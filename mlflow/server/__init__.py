import os
import shlex

from flask import Flask, send_from_directory
import gunicorn.app.base


from mlflow.server import handlers
from mlflow.server.handlers import get_artifact_handler
from mlflow.utils.process import exec_cmd

FILE_STORE_ENV_VAR = "MLFLOW_SERVER_FILE_STORE"
ARTIFACT_ROOT_ENV_VAR = "MLFLOW_SERVER_ARTIFACT_ROOT"
STATIC_PREFIX_ENV_VAR = "MLFLOW_STATIC_PREFIX"

REL_STATIC_DIR = "js/build"
app = Flask(__name__, static_folder=REL_STATIC_DIR)
STATIC_DIR = os.path.join(app.root_path, REL_STATIC_DIR)

for http_path, handler, methods in handlers.get_endpoints():
    app.add_url_rule(http_path, handler.__name__, handler, methods=methods)


def _add_static_prefix(route):
    prefix = os.environ.get(STATIC_PREFIX_ENV_VAR)
    if prefix:
        return prefix + route
    return route


# Serve the "get-artifact" route.
@app.route(_add_static_prefix('/get-artifact'))
def serve_artifacts():
    return get_artifact_handler()


# Serve the font awesome fonts for the React app
@app.route(_add_static_prefix('/webfonts/<path:path>'))
def serve_webfonts(path):
    return send_from_directory(STATIC_DIR, os.path.join('webfonts', path))


# We expect the react app to be built assuming it is hosted at /static-files, so that requests for
# CSS/JS resources will be made to e.g. /static-files/main.css and we can handle them here.
@app.route(_add_static_prefix('/static-files/<path:path>'))
def serve_static_file(path):
    return send_from_directory(STATIC_DIR, path)


# Serve the index.html for the React App for all other routes.
@app.route(_add_static_prefix('/'))
def serve():
    return send_from_directory(STATIC_DIR, 'index.html')


class Server(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.application = app
        self.options = options
        super(Server, self).__init__()

    def load_config(self):
        config = dict([(key, value) for key, value in self.options.items()
                       if key in self.cfg.settings and value is not None])
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

def _run_server(file_store_path, default_artifact_root, host, port, workers, static_prefix,
                gunicorn_opts=None):
    """
    Run the MLflow server, loaded by Gunicorn using a BaseApplication.
    :param static_prefix: If set, the index.html asset will be served from the path static_prefix.
                          If left None, the index.html asset will be served from the root path.
    :return: None
    """
    if file_store_path:
        os.environ[FILE_STORE_ENV_VAR] = file_store_path
    if default_artifact_root:
        os.environ[ARTIFACT_ROOT_ENV_VAR] = default_artifact_root
    if static_prefix:
        os.environ[STATIC_PREFIX_ENV_VAR] = static_prefix

    # Gunicorn options
    options = dict()
    options['bind'] = "%s:%s" % (host, port)
    if workers:
        options['workers'] = workers
    Server(app, options).run()

