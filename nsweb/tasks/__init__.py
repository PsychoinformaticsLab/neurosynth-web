from celery import Task
from nsweb.initializers import settings
from neurosynth.base.dataset import Dataset
from celery.utils import cached_property
import numpy as np
import pandas as pd
import nibabel as nb
import matplotlib.pyplot as plt
import seaborn as sns
from nilearn.image import resample_img
from nsweb.core import celery
from os.path import join, basename, exists
from nsweb.tasks.scatterplot import scatter


def load_image(dataset, filename):
    filename = join(settings.IMAGE_UPLOAD_DIR, filename)
    img = check_image(filename)
    return dataset.masker.mask(img)

def check_image(img):
    """ Check an image's dimensions and resample to the correct orientation/size """
    if isinstance(img, basestring):
        img = nb.load(img)
        # resample image if it's not the right shape
    if img.shape[:3] != (91, 109, 91):
        img = resample_img(img, target_affine=decode_image.anatomical.get_affine(), 
                target_shape=(91, 109, 91))
    return img

def get_decoder_feature_data(dd, feature):
    """ Get feature's data: check in the decoder DataFrame first, and if not found, 
    read from file (updating the in-memory DF). """
    if feature not in dd.columns:
            target_file = join(settings.IMAGE_DIR, 'features', feature + '_pFgA_z.nii.gz')
            if not exists(target_file):
                return False
            dd[feature] = load_image(make_scatterplot.dataset, target_file)
    return dd[feature].values

class NeurosynthTask(Task):

    @cached_property
    def dataset(self):
        return Dataset.load(settings.PICKLE_DATABASE)

    @cached_property
    def dd(self):  # decoding data
        return pd.read_msgpack(settings.DECODING_DATA)

    @cached_property
    def anatomical(self):
        f = join(settings.ROOT_DIR, 'data', 'images', 'anatomical.nii.gz')
        return nb.load(f)

    @cached_property
    def masks(self):
        maps = {
            'cortex': '/Users/tyarkoni/Dropbox/AllenSynth/Images/Masks/cortex.nii',
            'subcortex': '/Users/tyarkoni/Dropbox/AllenSynth/Images/Masks/subcortex_drewUpdated.nii',
            'hippocampus': '/Users/tyarkoni/Dropbox/AllenSynth/Images/Masks/FSL_BHipp_thr0.nii.gz',
            'accumbens': '/Users/tyarkoni/Dropbox/AllenSynth/Images/Masks/FSL_BNAcc_thr0.nii',
            'amygdala': '/Users/tyarkoni/Dropbox/AllenSynth/Images/Masks/FSL_BAmyg_thr0.nii',
            'putamen': '/Users/tyarkoni/Dropbox/AllenSynth/Images/Masks/FSL_BPut_thr0.nii.gz',
            'min4': '/Volumes/data/AllenSynth/Data/Maps/voxel_counts_r6.nii.gz'
        }
        for m, img in maps.items():
            maps[m] = load_image(self.dataset, img)
        return maps

@celery.task(base=NeurosynthTask)
def count_studies(feature, threshold=0.001, **kwargs):
    ids = count_studies.dataset.get_ids_by_features(str(feature), threshold=threshold)
    return len(ids)

@celery.task(base=NeurosynthTask)
def save_uploaded_image(filename, **kwargs):
    pass
    
@celery.task(base=NeurosynthTask)
def decode_image(filename, **kwargs):
    try:
        basefile = basename(filename)
        # Need to fix this--should probably add a "decode_id" field storing a UUID for 
        # any model that needs to be decoded but isn't an upload.
        uuid = 'gene_' + basefile.split('_')[2] if basefile.startswith('gene') else basefile[:32]
        dataset, dd = decode_image.dataset, decode_image.dd
        data = load_image(dataset, filename)
        r = np.corrcoef(data.T, dd.values.T)[0,1:]
        outfile = join(settings.DECODING_RESULTS_DIR, uuid + '.txt')
        pd.Series(r, index=dd.columns).to_csv(outfile, sep='\t')
    except Exception, e:
        print e
        print e.message
        return False

@celery.task(base=NeurosynthTask)
def make_scatterplot(filename, feature, base_id, outfile=None, n_voxels=None, allow_nondecoder_features=False, 
                    x_lab="Uploaded Image", y_lab=None, gene_masks=False, **kwargs):
    """ Make scatterplot """
    try:
        # Get the data
        x = load_image(make_scatterplot.dataset, filename)
        y = get_decoder_feature_data(make_scatterplot.dd, feature)

        # Subsample random voxels
        if n_voxels is not None:
            voxels = np.random.choose(np.arange(len(x)), n_voxels)
            x, y = x[voxels], y[voxels]

        # Set filename if needed
        if outfile is None:
            outfile = join(settings.DECODING_SCATTERPLOTS_DIR, base_id + '_' + feature + '.png')

        # Generate and save scatterplot
        if y_lab is None:
            y_lab='%s meta-analysis (z-score)' % feature
        masks = make_scatterplot.masks
        
        if gene_masks:
            spatial_masks = [masks['subcortex']]
            region_labels = ['hippocampus', 'accumbens', 'amygdala', 'putamen']
            voxel_count_mask = masks['min4']
        else:
            spatial_masks = None
            region_labels = ['cortex', 'subcortex']
            voxel_count_mask = None

        region_masks = [masks[l] for l in region_labels]

        scatter(x, y, region_masks=region_masks, mask_labels=region_labels, unlabeled_alpha=0.15,
                        alpha=0.5, fig_size=(12,12), palette='Set1', x_lab=x_lab, 
                        y_lab=y_lab, savefile=outfile, spatial_masks=spatial_masks,
                        voxel_count_mask=voxel_count_mask)

    except Exception, e:
        print e
        print e.message
        return False
