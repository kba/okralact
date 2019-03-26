from flask import render_template, redirect, url_for, request, send_file
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SubmitField, SelectField
from werkzeug.utils import secure_filename
from app import app
from app.lib.process_file import rename_file
from rq.job import Job
import tarfile
import shutil
import os
import sys
from engines.validate_parameters import valiadte_string


parentdir = os.getcwd().rsplit('/', 1)[0]
print(parentdir)
sys.path.insert(0, parentdir)


def get_files():
    files_list = os.listdir(app.config['UPLOAD_FOLDER'])
    return files_list


def get_configs():
    configs_list = os.listdir(app.config['CONFIG_FOLDER'])
    return configs_list


def get_engines():
    return ["kraken", "ocropus", "tesseract", "calamari"]


def get_options(file_list):
    nconfig = len(file_list)
    choices = []
    for i in range(nconfig):
        choices.append((str(i), file_list[i]))
    return choices


def get_file_status():
    dict_status = {}
    for job_id in app.job_id2file:
        job = Job.fetch(job_id, app.redis)
        filename, config = app.job_id2file[job_id]
        dict_status[(filename, config)] = job.status
    return dict_status


class UploadDataForm(FlaskForm):
    archive = FileField(validators=[FileAllowed(set(['tar.gz'])), FileRequired(u'Choose a file!')])
    submit = SubmitField(u'upload')


class UploadConfigForm(FlaskForm):
    archive = FileField(validators=[FileAllowed(set(['json'])), FileRequired(u'Choose a file!')])
    submit = SubmitField(u'upload')


class SelectConfigForm(FlaskForm):
    config_choices = get_options(get_configs())
    select_config = SelectField(u'config', choices=config_choices)
    data_choices = get_options(get_files())
    select_data = SelectField(u'data', choices=data_choices)
    submit = SubmitField(u'run')


# Manage Files
@app.route('/data', methods=['GET', 'POST'])
def manage_data():
    files_list = get_files()
    form = UploadDataForm()
    f = form.archive.data
    if form.validate_on_submit():
        filename = secure_filename(f.filename)
        prefix = '.'.join(filename.rsplit('.', 2)[:-2])
        filename = rename_file(prefix, '.tar.gz', files_list)
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return redirect(url_for('manage_data'))
    return render_template('data.html', form=form, files_list=files_list)


# Manage Files
@app.route('/configs', methods=['GET', 'POST'], defaults={'error_message': ''})
@app.route('/configs/<error_message>', methods=['GET', 'POST'])
def manage_configs(error_message):
    configs_list = get_configs()
    form = UploadConfigForm()
    f = form.archive.data
    errors = error_message.split('\n')
    print(errors)
    print(error_message)
    if form.validate_on_submit():
        content = f.read()
        errors = valiadte_string(content)
        print(errors)
        if len(errors) > 0:
            print('print_error')
            return redirect(url_for('manage_configs', error_message='\n'.join(errors)))
        else:
            filename = secure_filename(f.filename)
            prefix = filename.rsplit('.')[0]
            filename = rename_file(prefix, '.json', configs_list)
            f.save(os.path.join(app.config['CONFIG_FOLDER'], filename))
            return redirect(url_for('manage_configs'))
    return render_template('configs.html', errors=errors, form=form, files_list=configs_list)


@app.route('/delete_data/<filename>')
def delete_data(filename):
    if filename in app.job_file2id:
        app.job_file2id.pop(filename, None)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.remove(file_path)
    prefix = filename.rsplit('.', 2)[0]
    model_file = os.path.join(os.getcwd(), 'engines/model', 'model_%s' % filename)
    if os.path.exists(model_file):
        os.remove(model_file)
    model_folder = os.path.join(os.getcwd(), 'engines/model', prefix)
    if os.path.exists(model_folder):
        shutil.rmtree(model_folder, ignore_errors=True)
    return redirect(url_for('manage_data'))


@app.route('/delete_config/<filename>')
def delete_config(filename):
    if filename in app.job_file2id:
        app.job_file2id.pop(filename, None)
    file_path = os.path.join(app.config['CONFIG_FOLDER'], filename)
    os.remove(file_path)
    return redirect(url_for('manage_configs'))


# Manage jobs
@app.route('/jobs', methods=['GET', 'POST'])
def manage_job():
    dict_status = get_file_status()
    print(app.job_file2id)
    print(dict_status)
    form = SelectConfigForm()
    if request.method == 'POST':
        data_choices = dict(get_options(get_files()))
        config_choices = dict(get_options(get_configs()))
        select_config = config_choices.get(form.select_config.data)
        select_data = data_choices.get(form.select_data.data)
    #     redirect(url_for('manage_job'))
        print('data', select_data)
        print('config:', select_config)
        return redirect(url_for('train_model', filename=select_data, config=select_config))
    return render_template('jobs.html', form=form, dict_status=dict_status)


# Run jobs
@app.route('/run', methods=['POST', 'GET'])
def train_model():
    print('train_model')
    filename = request.args.get('filename', None)
    config = request.args.get('config', None)

    print(filename, config)
    # form = SelectConfigForm()
    if (filename, config) not in app.job_file2id:
        job = app.task_queue.enqueue('train.train_from_file', '../static/data/%s' % filename)
        job_id = job.get_id()
        app.job_file2id[(filename, config)] = job_id
        app.job_id2file[job_id] = (filename, config)
    print(app.job_id2file)
    # files_list = os.listdir(app.config['UPLOAD_FOLDER'])
    return redirect(url_for('manage_job'))


# download models
@app.route('/download/<filename>')
def download(filename):
    prefix = filename.rsplit('.', 2)[0]
    model_dir = os.path.join(os.getcwd(), 'engines/model/')
    model_files = os.listdir(os.path.join(model_dir, prefix))
    outfile = os.path.join(model_dir, 'model_%s.tar.gz' % prefix)
    if os.path.exists(outfile):
        os.remove(outfile)
    with tarfile.open(outfile, "w:gz") as _tar:
        for fn in model_files:
            new_fn = os.path.join(model_dir, prefix, fn)
            _tar.addfile(tarfile.TarInfo('model/%s' % fn), open(new_fn))
    return send_file(outfile, mimetype='text/tar', attachment_filename='model.tar.gz', as_attachment=True)


# Manual of Using OCR Engines
@app.route('/manual')
def manual():
    return render_template('manual.html')

