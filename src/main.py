"""Entrypoint do no distribuido.
"""

from src.node import Node


def main():
    node = Node()
    node.start()


if __name__ == "__main__":
    main()
