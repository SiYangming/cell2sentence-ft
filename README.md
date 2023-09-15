# Cell2Sentence

Cell2Sentence is a novel method for adapting large language models to single-cell transcriptomics. We transform single-cell RNA sequencing data into sequences of gene names ordered by expression level, termed "cell sentences". This repository provides scripts and examples for converting cells to cell sentences, fine-tuning language models, and converting outputs back to expression values.

![Overview](https://github.com/vandijklab/cell2sentence-ft/blob/main/Overview.png)



## Quickstart

1. Download the data subset used in the example here:
    - Domínguez Conde, C., et al. [Cross-tissue immune cell analysis reveals tissue-specific features in humans](https://drive.google.com/file/d/1PYUM59fKclw-aeN79oL5ghCkU4kn6XvN/view?usp=sharing)
    - Place the data in the root of the data repository

2. Run preprocessing: `python preprocessing.py`

3. Run `python create_cell_sentence_arrow_dataset.py`
