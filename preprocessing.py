"""
This script will load a raw single-cell dataset, preprocess and normalize the data, and then
run the conversion to cell sentences. Output files will be placed in the same directory.
"""
import os

import anndata
import numpy as np
import scanpy as sc
import pandas as pd
import sklearn.linear_model as lm
import plotnine as pn
from sklearn.metrics import r2_score
from sklearn.utils import shuffle
from scipy.stats import pearsonr, spearmanr
from tqdm import tqdm

from src.cell2sentence import transforms
from src.cell2sentence.integrations import xlm_prepare_outpath

# Huggingface transformers dataset library
from datasets import Dataset

BASE10_THRESHOLD = 3
RANDOM_SEED = 42
SUBSAMPLE = False
NUM_SUBSAMPLE = 10000  # If subsampling raw data, how many cells to keep


def normalize_and_rank_transform(data_matrix_X, normalize=True):
    """
    Helper function which accepts a data matrix, optionally row-normalizes it, 
    and calculated a rank transformation of the data.

    Args:
        data_matrix_X:  numpy matrix of shape [num_cells, num_genes]
        normalize:      boolean flag for whether to normalize data

    Returns:
        data_matrix_X:  normalized data matrix
        rank_matrix_X:  matrix of rank values for each cell, shame shape as data_matrix_X
    """
    if normalize:
        normalized_data_matrix_X = np.diag(10000 / np.ravel(np.sum(data_matrix_X, axis=1))) @ data_matrix_X
        data_matrix_X = np.asarray(normalized_data_matrix_X)

    rank_matrix_X = np.zeros(shape=data_matrix_X.shape)
    for i in tqdm(range(data_matrix_X.shape[0])):
        cols = np.ravel(range(data_matrix_X.shape[1]))
        vals = np.ravel(data_matrix_X[i, :])
        cols, vals = shuffle(cols, vals)
        ranks = cols[np.argsort(-vals, kind="stable")]
        for j in range(len(ranks)):
            rank_matrix_X[i, ranks[j]] = j
    
    return data_matrix_X, rank_matrix_X


def calculate_transformation_metrics(df, plotting_sample_size=10000):
    """
    Helper function which takes as input a pandas DataFrame of expression values and
    ranks, and fits a linear regression model to predict back expression value from 
    log rank. 
    
    Plots are created to show the relationship between log rank and log expression,
    as well as the performance of expression reconstruction by the linear model. 
    Metrics for expression reconstruction, as well as the parameters of the linear
    model are saved in a CSV file.

    Args:
        df:                     pandas DataFrame with keys: 'preprocessed_transcript_count, 
                                    'preprocessed_rank', 'log_preprocessed_transcript_count', 
                                    and 'log_preprocessed_rank'
        plotting_sample_size:   how many values to sample for plotting
    
    Steps:
        1. Fit linear regression to predict back expression from log rank
        2. 
    

    """
    # (1) Fit linear regression between log rank (x-axis) and log expression (y-axis)
    x_axis_name = "log_preprocessed_rank"
    y_axis_name = "log_preprocessed_transcript_count"
    x = np.array(df.loc[df[x_axis_name] < BASE10_THRESHOLD, x_axis_name]).reshape(-1, 1)
    y = df.loc[df[x_axis_name] < BASE10_THRESHOLD, y_axis_name]

    reg = lm.LinearRegression().fit(x, y)

    # Plot relationship
    plot = (pn.ggplot(
                df.sample(plotting_sample_size),
                pn.aes(x="log_preprocessed_rank", y="log_preprocessed_transcript_count"),
            )
            + pn.geom_abline(slope=reg.coef_, intercept=reg.intercept_, color="red")
            + pn.geom_point(color="blue", size=0.5)
            + pn.labs(
                x="Gene Log Rank",
                y="Gene Log Expression",
                title="Log Rank vs Log Expression",
            ))
    plot.save(os.path.join(CURRENT_DIR, "plot_log_rank_vs_log_expr.png"), dpi=300)

    # (2) Reconstruct expression from log rank, calculate reconstruction performance metrics
    rank_reconstructed_X = reg.predict(np.array(df["log_preprocessed_rank"]).reshape(-1, 1))

    r_squared_score = r2_score(
        np.asarray(df["log_preprocessed_transcript_count"]),
        np.asarray(rank_reconstructed_X),
    )
    pearson_r_score = pearsonr(
        np.asarray(df["log_preprocessed_transcript_count"]),
        np.asarray(rank_reconstructed_X),
    )
    spearman_r_score = spearmanr(
        np.asarray(df["log_preprocessed_transcript_count"]),
        np.asarray(rank_reconstructed_X),
    )

    reconstructed_expr_values_df = pd.DataFrame({
        "Ground Truth Expression": df["log_preprocessed_transcript_count"],
        "Reconstructed Expression from Log Rank": rank_reconstructed_X,
    })
    plot = (
        pn.ggplot(
            reconstructed_expr_values_df.sample(plotting_sample_size),
            pn.aes(x="Ground Truth Expression", y="Reconstructed Expression from Log Rank"),
        )
        + pn.geom_point(color="blue", size=0.5)
        + pn.geom_abline(slope=1, intercept=0, color="red")
        + pn.labs(
            x="Ground Truth Expression",
            y="Reconstructed Expression from Log Rank",
            title="Ground Truth Expression vs Reconstruction from Rank",
        )
    )
    plot.save(os.path.join(CURRENT_DIR, "plot_gt_expr_vs_reconstructed_expr_from_rank.png"), dpi=300)

    # 3. Create results dataframe and return
    metrics_df = pd.DataFrame({
        "threshold": [BASE10_THRESHOLD],
        "slope": [reg.coef_.item()],
        "intercept": [reg.intercept_.item()],
        "R^2": [r_squared_score.item()],
        "Pearson_R_statistic": [pearson_r_score.statistic.item()],
        "Pearson_R_p_value": [pearson_r_score.pvalue.item()],
        "Spearman_R_statistic": [spearman_r_score.statistic.item()],
        "Spearman_R_p_value": [spearman_r_score.pvalue.item()],
    })
    metrics_df.to_csv(os.path.join(CURRENT_DIR, "transformation_metrics_and_parameters.csv"))


def main():
    #--- Load data ---#
    print("Loading raw data...")
    adata = anndata.read_h5ad(DATA_PATH)

    # Raw transcript counts may be contained in the .raw attribute
    if adata.raw is not None:
        adata.X = adata.raw.X

    # Key 'feature_name' contains the names of each gene. Make gene names the index of adata.var
    adata.var["feature_name"] = adata.var["feature_name"].astype(str)
    adata.var['ensembl_ids'] = adata.var.index
    adata.var_names = adata.var["feature_name"]  # Changes .var index
    adata.var_names_make_unique(join="_")

    print(f"Done loading data: {adata}")

    # Subsample if processing a subset of the raw data
    if SUBSAMPLE:
        print(f"\nSubsampling adata to {NUM_SUBSAMPLE} samples.")
        sc.pp.subsample(adata, n_obs=NUM_SUBSAMPLE, random_state=RANDOM_SEED)

    #--- Standard Filtering Steps: https://scanpy-tutorials.readthedocs.io/en/latest/pbmc3k.html ---#
    print(f"\nFiltering: starting with data shape: {adata.shape}")
    sc.pp.filter_cells(adata, min_genes=200)
    sc.pp.filter_genes(adata, min_cells=3)

    # annotate the group of mitochondrial genes as 'mt'
    adata.var["mt"] = adata.var_names.str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True)

    adata = adata[adata.obs.n_genes_by_counts < 2500, :]
    adata = adata[adata.obs.pct_counts_mt < 20, :]

    print(f"Filtering finished, shape: {adata.shape}")

    #--- Normalization and Rank Transformation ---#
    print("\nNormalization and Rank Transformation")
    raw_X = np.copy(adata.X.toarray())
    norm_X, rank_norm_X = normalize_and_rank_transform(np.copy(adata.X.todense()), normalize=True)
    adata.X = np.log10(1 + norm_X)  # Update adata object with normalized expression

    # Create dataframe of ranks and expression values for plotting
    expr_and_rank_df = pd.DataFrame({
        "raw_transcript_count": np.ravel(raw_X),
        "preprocessed_transcript_count": np.ravel(norm_X),
        "preprocessed_rank": np.ravel(rank_norm_X),
        "log_preprocessed_transcript_count": np.log10(1 + np.ravel(norm_X)),
        "log_preprocessed_rank": np.log10(1 + np.ravel(rank_norm_X))
    })
    # Remove rows where raw expression is 0
    expr_and_rank_df = expr_and_rank_df[expr_and_rank_df["raw_transcript_count"] != 0]

    #--- Plot Scatterplots, Benchmark Relationship Between Rank and Expression ---#
    print("\nPlotting and Benchmarking starting...")
    calculate_transformation_metrics(df=expr_and_rank_df, plotting_sample_size=10000)

    #--- Create Cell Sentences, Save to Disk ---#
    print("\nFinished. Writing cell sentences and adata to disk...")
    adata.write_h5ad(os.path.join(CURRENT_DIR, "preprocessed_adata.h5ad"))
    csdata = transforms.csdata_from_adata(adata)
    xlm_prepare_outpath(csdata, os.path.join(CURRENT_DIR, "cell_sentences"), species_tag="human")

    print("Done.")


if __name__ == "__main__":
    CURRENT_DIR = os.getcwd()
    DATA_PATH = os.path.join(CURRENT_DIR, "raw_data_subset.h5ad")
    main()
