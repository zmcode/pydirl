import os
import logging
import errno

from flask import Flask, safe_join, send_file, render_template, \
        abort, request, redirect
from flask_bootstrap import Bootstrap

from .files_utils import get_folder_infos, get_file_infos
from .tools import gevent_run, init_loggers, stream_zipped_dir


def create_app(conf={}):
    app = Flask('pydirl')
    app.config.update(
            DEBUG=True,
            ADDRESS='0.0.0.0',
            PORT='5000',
            BOOTSTRAP_SERVE_LOCAL=True,
            ROOT=os.curdir,
            FOLDER_SIZE=False,
            LAST_MODIFIED=False
        )

    app.config.update(conf)

    '''dirty trick: prevent default flask handler to be created
      in flask version > 0.10.1 will be a nicer way to disable default loggers
      tanks to this new code mitsuhiko/flask@84ad89ffa4390d3327b4d35983dbb4d84293b8e2
    '''
    app._logger = logging.getLogger(app.import_name)

    Bootstrap(app)

    app.root = os.path.abspath(app.config['ROOT'])
    app.logger.debug("Serving root: '{0}'".format(app.root))

    @app.route('/favicon.ico')
    def favicon():
        abort(404)

    @app.route('/', defaults={'relPath': ''})
    @app.route('/<path:relPath>')
    def folder_route(relPath):
        path = safe_join(app.root, relPath)
        app.logger.debug("Absolute requested path: '{0}'".format(path))

        if os.path.isfile(path):
            return send_file(path)

        if os.path.isdir(path):
            if relPath and relPath[-1] != '/':
                return redirect(relPath + '/', code=302)
            elif 'download' in request.args:
                zipName = os.path.basename(path) if relPath else 'archive'
                return stream_zipped_dir(path, zipName)

        entries = {'dirs': {}, 'files': {}}
        for e in os.listdir(path):
            e_path = os.path.join(path, e)
            if os.path.isdir(e_path):
                entries['dirs'][e] = get_folder_infos(e_path, recursive=app.config['FOLDER_SIZE'])
            elif os.path.isfile(e_path):
                entries['files'][e] = get_file_infos(e_path)
            else:
                app.logger.debug('Skipping unknown element: {}'.format(e))
        relDirs = [f for f in relPath.split(os.sep) if f]
        return render_template('template.html', entries=entries, relPath=relPath, relDirs=relDirs)

    @app.errorhandler(OSError)
    def oserror_handler(e):
        if app.config['DEBUG']:
            app.logger.exception(e)
        else:
            app.logger.error(e)

        if e.errno in [errno.ENOENT, errno.ENOTDIR]:
            # no such file or directory
            errCode = 404
        elif e.errno == errno.EACCES:
            # permission denied
            errCode = 403
        else:
            errCode = 500
        return render_template('error.html', message=e.strerror, code=errCode), errCode

    return app


def main(conf={}):
    init_loggers(logNames=['pydirl', 'werkzeug'],
                 logLevel=logging.DEBUG if conf.get('DEBUG', False) else logging.INFO)
    app = create_app(conf)
    gevent_run(app,
               address=app.config.get('ADDRESS'),
               port=int(app.config.get('PORT')),
               reloader=app.config.get('DEBUG'),
               debugger=app.config.get('DEBUG'))


if __name__ == "__main__":
    main()
