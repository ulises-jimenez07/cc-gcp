"""
Generic Word Count MapReduce job for Hadoop Streaming.
Used in Tutorial 1.1: Dataproc & MapReduce.

Usage (Local Simulation):
  cat file.txt | python3 word_count.py --mode=mapper | sort -k1,1 | python3 word_count.py --mode=reducer
"""

import sys
import argparse


def mapper():
    """Emit generic (word, 1) pairs from any text input."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        # Split by whitespace and emit (word, 1)
        words = line.split()
        for word in words:
            # Clean punctuation and lowercase for better results
            clean_word = "".join(filter(str.isalnum, word)).lower()
            if clean_word:
                print(f"{clean_word}\t1")


def reducer():
    """Sum counts for each word key (input must be sorted by key)."""
    current_word = None
    current_count = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            word, count = line.split("\t", 1)
            count = int(count)
        except ValueError:
            continue

        if word == current_word:
            current_count += count
        else:
            if current_word:
                print(f"{current_word}\t{current_count}")
            current_word = word
            current_count = count

    # Output the last word
    if current_word:
        print(f"{current_word}\t{current_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["mapper", "reducer"], required=True)
    args = parser.parse_args()

    if args.mode == "mapper":
        mapper()
    else:
        reducer()
