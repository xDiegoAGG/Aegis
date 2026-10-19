from cluster import reset


# Stops any load and leaves 1 pod with the Aegis HPA, for example between two demos.
def main():
    reset("aegis")


if __name__ == "__main__":
    main()
