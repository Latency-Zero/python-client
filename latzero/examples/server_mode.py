"""
Example: connect to a running latzero-server.
"""

from latzero import LatZero


def main():
    with LatZero("latzero://example-client", pool="demo") as client:
        client.set("greeting", {"message": "hello from server mode"}, persistent=True)
        print(client.get("greeting"))


if __name__ == "__main__":
    main()
