"""Ukázkový nástroj pro Dvojpanel: vypíše předané soubory a jejich velikost."""
import os
import sys


def main():
    files = sys.argv[1:]
    if not files:
        print("Nebyl předán žádný soubor.")
        return 1
    for path in files:
        size = f"{os.path.getsize(path):,}".replace(",", " ")
        print(f"{os.path.basename(path)}: {size} B")
    print(f"Celkem souborů: {len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
