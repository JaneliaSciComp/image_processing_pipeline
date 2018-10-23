from flask_script import Manager
from app import app


manager = Manager(app)


@manager.option('-b', '--binding-host',
                dest='host',
                default='localhost',
                required=False)
@manager.option('-p', '--port', dest='port', default=9000, type=int, required=False)
def runserver(host='localhost', port=9000):
    app.run(host=host, port=port)


if __name__ == '__main__':
    manager.run()
