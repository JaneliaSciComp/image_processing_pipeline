import argparse

from app import app


def runserver(host='localhost', port=9000):
    app.run(host=host, port=port)


def main():
    args_parser = argparse.ArgumentParser()

    args_parser.add_argument('-b', '--binding',
                             dest='binding',
                             type=str,
                             default='localhost',
                             help='binding address')
    args_parser.add_argument('-p', '--port',
                             dest='port',
                             type=int,
                             default=9000,
                             help='port number')
    args = args_parser.parse_args()
    runserver(host=args.binding, port=args.port)


if __name__ == '__main__':
    runserver()
