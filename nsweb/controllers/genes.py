from flask import Blueprint, render_template, redirect, url_for, request, jsonify, abort, send_file
from nsweb.models import Feature, Gene
from nsweb.core import add_blueprint
from nsweb.tasks import decode_image, make_scatterplot
from nsweb.initializers import settings
from flask.helpers import url_for
import simplejson as json
import re
from glob import glob
from os.path import join, basename, exists

bp = Blueprint('genes',__name__,url_prefix='/genes')

@bp.route('/')
def index():
    return render_template('genes/index.html.slim')

@bp.route('/<string:val>/')
def show(val):
    images = [{
        'name': val,
        'url': url_for('genes.get_image', val=val),
        'colorPalette': 'red'
    }]
    print images
    return render_template('genes/show.html.slim', gene=val, images=json.dumps(images))

@bp.route('/<string:val>/image')
def get_image(val):
    gene = Gene.query.filter_by(symbol=val).first()
    if gene is None: abort(404)
    img = gene.images[0].image_file
    return send_file(img, as_attachment=True,
            attachment_filename=gene.symbol + '_AHBA.nii.gz')

@bp.route('/<string:val>/decode')
def get_data(val):
    gene = Gene.query.filter_by(symbol=val).first()
    if gene is None: abort(404)
    decode_file = 'gene_' + gene.symbol + '.txt'
    filename = join(settings.DECODING_RESULTS_DIR, decode_file)
    if not exists(filename):
        result = decode_image.delay(gene.images[0].image_file).wait()  # decode image
    data = open(filename).read().splitlines()
    data = [x.split('\t') for x in data]
    data = [{'feature': f, 'r': round(float(v), 3)} for (f, v) in data]
    return jsonify(data=data)
    
@bp.route('/<string:val>/scatter/<string:feature>.png')
def get_scatter(val, feature):
    outfile = join(settings.DECODING_SCATTERPLOTS_DIR, val + '_' + feature + '.png')
    if not exists(outfile):
        """ Return .png of scatter plot between the uploaded image and specified feature. """
        gene = Gene.query.filter_by(symbol=val).first()
        if gene is None: abort(404)
        result = make_scatterplot.delay(gene.images[0].image_file, feature, gene.symbol,
            x_lab='%s expression level' % gene.symbol, outfile=outfile, gene_masks=True).wait()
    return send_file(outfile, as_attachment=False, 
            attachment_filename=basename(outfile))

add_blueprint(bp)