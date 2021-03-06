import surfer
from surfer import Brain
import numpy as np
import nibabel as nb
import nipype.interfaces.freesurfer as fs
#from variables import freesurferdir, resultsdir
import os
import glob
import sys

def annotation():
	brain.add_annotation('aparc.a2009s', alpha = .2)
def roi():
	brain.add_label('prefrontal', alpha = .4)
def save(filename):
	brain.save_montage(filename+'.png',['med', 'lat', 'ros', 'vent'],orientation = 'h') #to save png
def all_brains(dir):
    for root, dirs, filenames in os.walk(dir):
        for f in filenames:
            hemi = f[:2]
            if hemi == 'De' or hemi == 'te':
                hemi = 'lh'
            if f.endswith('nii'):
                print f, hemi
                clustermap = nb.load(os.path.join(root,f)).get_data()
                add_cluster(clustermap, hemi)
                save(os.path.join(root,f))

def find_cluster(subject_id,hemi,sim,cluster_type,n_clusters,session):
    filestring = '/media/sf_Volumes/clustered/_hemi_{0}/_session_{1}/_subject_id_{2}/_sim_{3}/_cluster_{4}/_n_clusters_{5}'
    #filepath = resultsdir+filestring.format(hemi,session,subject_id,sim,cluster_type,n_clusters)
    filepath = filestring.format(hemi,session,subject_id,sim,cluster_type,n_clusters)
    os.chdir(filepath)
    clustermap = nb.load(''.join(glob.glob('*.nii'))).get_data()
    add_cluster(clustermap, hemi)

def click_thru(filedir, hemi, n):
    clustermap = nb.load(glob.glob(filedir+'_n_clusters_'+str(n)+'/*.nii')).get_data()
    add_cluster(clustermap, hemi)

def add_cluster(clustermap, hemi):
    brain = Brain(subject_id, hemi, surface,config_opts=dict(background="lightslategray", cortex="high_contrast"))
    brain.add_data(clustermap, colormap='spectral', alpha=.8)
    brain.data['colorbar'].number_of_colors = int(clustermap.max())+1
    brain.data['colorbar'].number_of_labels = int(clustermap.max())+1 ##because -1 denotes masked regions, cluster labels start at 1

if __name__ == '__main__' :
	#fs.FSCommand.set_default_subjects_dir('SCR/data/Final_High')#(freesurferdir)
	#pysurfer visualization
    subject_id = 'fsaverage4'
    hemi = 'lh'
    surface = 'pial'
    brain = Brain(subject_id, hemi, surface, config_opts=dict(background="lightslategray", cortex="high_contrast"))
    print('FORMAT: add_cluster(clustermap,hemisphere)\nfind_cluster(subject_id,hemi,sim,cluster_type,n_clusters,session)')
