import os
from datasets import Dataset


def create_partition_arrow_ds(filename, data_split="train"):
    assert data_split in ['train', 'val', 'test'], "Unknown dataset split specified."
    with open(filename) as fp:
        sentences_list = [line.rstrip() for line in fp]
    
    arrow_dict = { "input_ids": sentences_list }

    arrow_ds = Dataset.from_dict(arrow_dict)
    arrow_ds.save_to_disk(os.path.join(OUTPUT_DIR, f"{data_split}_arrow_ds"))



def main():
    create_partition_arrow_ds(filename=os.path.join(CELL_SENTENCES_DIR, "train_human.txt"), data_split="train")
    create_partition_arrow_ds(filename=os.path.join(CELL_SENTENCES_DIR, "valid_human.txt"), data_split="val")
    create_partition_arrow_ds(filename=os.path.join(CELL_SENTENCES_DIR, "test_human.txt"), data_split="test")


if __name__ == "__main__":
    # CURRENT_DIR = os.getcwd()
    CURRENT_DIR = "/home/sr2464/Desktop/cell2sentence-ft"
    CELL_SENTENCES_DIR = os.path.join(CURRENT_DIR, "cell_sentences")
    OUTPUT_DIR = os.path.join(CURRENT_DIR, "cell_sentence_arrow_ds")
    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)
    
    main()
