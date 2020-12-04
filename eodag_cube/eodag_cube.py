import logging

LOGGER = logging.getLogger(__name__)


def hello_world():
    message = "hello world!"
    LOGGER.info(message)
    return message


def main():
    hello_world()


if __name__ == "__main__":
    main()
