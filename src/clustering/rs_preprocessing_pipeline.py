from __future__ import division

from nipype import config
config.enable_debug_mode()

import os
import matplotlib
matplotlib.use('Agg')
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
import nipype.interfaces.fsl as fsl
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.dcmstack as dcm

display = None
if "DISPLAY" in os.environ:
    display = os.environ["DISPLAY"]
    os.environ.pop("DISPLAY")
from bips.workflows.gablab.wips.scripts.base import create_rest_prep
if display:
    os.environ["DISPLAY"] = display
from bips.utils.reportsink.io import ReportSink
from nipype.utils.filemanip import list_to_filename

from variables import subjects, workingdir, preprocdir, freesurferdir, dicomdir, niftidir, construct_dicomfiledir, rs_preprocessing_dg_template, rs_preprocessing_dg_args, hemispheres

def create_preproc_report_wf(report_dir, name="preproc_report"):
    wf = pe.Workflow(name=name)
    
    inputspec = pe.Node(util.IdentityInterface(fields=['art_detect_plot', 
                                                       'mean_epi', 
                                                       'reg_file', 
                                                       'ribbon', 
                                                       'fssubjects_dir', 
                                                       'tsnr_file',
                                                       'report_name',
                                                       'subject_id']),
                        name="inputspec")
    
    def plot_epi_to_t1_coregistration(epi_file, reg_file, ribbon, fssubjects_dir):       
	import pylab as plt 
        from nipy.labs import viz
        import nibabel as nb
        import numpy as np
        import os
        import nipype.interfaces.freesurfer as fs
        anat = nb.load(ribbon).get_data()
        anat[anat > 1] = 1
        anat_affine = nb.load(ribbon).get_affine()
        func = nb.load(epi_file).get_data()
        func_affine = nb.load(epi_file).get_affine()
        fig = plt.figure(figsize=(8, 6), edgecolor='k', facecolor='k')
        slicer = viz.plot_anat(np.asarray(func), np.asarray(func_affine), black_bg=True,
                                cmap=plt.cm.spectral,
                                cut_coords=(-6,3,12),
                                figure=fig,
                                axes=[0, .50, 1, .33]
                                )
        slicer.contour_map(np.asarray(anat), np.asarray(anat_affine), levels=[.51], colors=['r',])
        slicer.title("Mean EPI with cortical surface contour overlay (before registration)", size=12,
                     color='w', alpha=0)
        
        res = fs.ApplyVolTransform(source_file = epi_file,
                                reg_file = reg_file,
                                fs_target = True,
                                subjects_dir = fssubjects_dir).run()
                          
        func = nb.load(res.outputs.transformed_file).get_data()
        func_affine = nb.load(res.outputs.transformed_file).get_affine()
        slicer = viz.plot_anat(np.asarray(func), np.asarray(func_affine), black_bg=True,
                                cmap=plt.cm.spectral,
                                cut_coords=(-6,3,12),
                                figure=fig,
                                axes=[0, 0, 1, .33]
                                )
        slicer.contour_map(np.asarray(anat), np.asarray(anat_affine), levels=[.51], colors=['r',])
        slicer.title("Mean EPI with cortical surface contour overlay (after registration)", size=12,
                     color='w', alpha=0)
        plt.savefig("reg_plot.png", facecolor=fig.get_facecolor(), edgecolor='none')
        return os.path.abspath("reg_plot.png")
    
    plot_reg = pe.Node(util.Function(function=plot_epi_to_t1_coregistration, 
                                     input_names=['epi_file', 'reg_file', 'ribbon', 'fssubjects_dir'], 
                                     output_names=['plot_file']), name="plot_reg")
    wf.connect(inputspec, "mean_epi", plot_reg, "epi_file")
    wf.connect(inputspec, "reg_file", plot_reg, "reg_file")
    wf.connect(inputspec, "ribbon", plot_reg, "ribbon")
    wf.connect(inputspec, "fssubjects_dir", plot_reg, "fssubjects_dir")
    
    plot_tsnr = pe.Node(fsl.Slicer(), name="plot_tsnr")
    plot_tsnr.inputs.all_axial = True
    plot_tsnr.inputs.image_width = 1000
    
    wf.connect(inputspec, "tsnr_file", plot_tsnr, "in_file")
    
    write_report = pe.Node(ReportSink(orderfields=["motion parameters", "tSNR", "coregistration"]), name="write_report")
    write_report.inputs.base_directory = report_dir
    
    def prepend_title(s_id):
        return "Resting state fMRI preprocessing report for " + s_id
    wf.connect(inputspec, ('subject_id', prepend_title),write_report, "report_name")
    wf.connect(inputspec, "art_detect_plot", write_report, "motion parameters")
    wf.connect(plot_tsnr, "out_file", write_report, "tSNR")
    wf.connect(plot_reg, "plot_file", write_report, "coregistration")
    
    return wf

def get_wf():
    import numpy as np

    wf = pe.Workflow(name="main_workflow")
    wf.base_dir = os.path.join(workingdir,"rs_preprocessing/")
    wf.config['execution']['crashdump_dir'] = wf.base_dir + "crash_files/"

##Infosource##    
    subject_id_infosource = pe.Node(util.IdentityInterface(fields=['subject_id']), name="subject_id_infosource")
    subject_id_infosource.iterables = ('subject_id', subjects)

    session_infosource = pe.Node(util.IdentityInterface(fields=['session']), name="session_infosource")
    session_infosource.iterables = ('session', sessions)

    hemi_infosource = pe.Node(util.IdentityInterface(fields=['hemi']), name="hemi_infosource")
    hemi_infosource.iterables = ('hemi',hemispheres)

##Datagrabber##
    datagrabber = pe.Node(nio.DataGrabber(infields=['subject_id'], outfields=['resting_nifti','t1_nifti','dicoms']), name="datagrabber", overwrite=True)
    datagrabber.inputs.base_directory = '/'
    datagrabber.inputs.template = '*'
    datagrabber.inputs.field_template = rs_preprocessing_dg_template
    datagrabber.inputs.template_args = rs_preprocessing_dg_args
    datagrabber.inputs.sort_filelist = True

    wf.connect(subject_id_infosource, 'subject_id', datagrabber, 'subject_id')
    wf.connect(session_infosource, 'session', datagrabber, 'session')

##DcmStack & MetaData##
    dicom_filedir = pe.Node(name='dicom_filedir', interface=util.Function(input_names=['subject_id','session'], output_names=['filedir'], function=construct_dicomfiledir))

    stack = pe.Node(dcm.DcmStack(), name = 'stack')
    stack.inputs.embed_meta = True

    tr_lookup = pe.Node(dcm.LookupMeta(), name = 'tr_lookup')
    tr_lookup.inputs.meta_keys = {'RepetitionTime':'TR'}

    wf.connect(subject_id_infosource, 'subject_id', dicom_filedir, 'subject_id')
    wf.connect(session_infosource, 'session', dicom_filedir, 'session')

    wf.connect(dicom_filedir, 'filedir', stack, 'dicom_files')        
    wf.connect(stack, 'out_file', tr_lookup, 'in_file')

##Preproc from BIPs##    
    preproc = create_rest_prep(name="bips_resting_preproc", fieldmap=False)
    zscore = preproc.get_node('z_score')
    preproc.remove_nodes([zscore])
    mod_realign = preproc.get_node('mod_realign')
    mod_realign.plugin_args = {'submit_specs':'request_memory=4000\n'}
    #workaround for realignment crashing in multiproc environment
    mod_realign.run_without_submitting = True


    # inputs
    preproc.inputs.inputspec.motion_correct_node = 'nipy'
    ad = preproc.get_node('artifactdetect')
    preproc.disconnect(mod_realign,'parameter_source',ad,'parameter_source')
    ad.inputs.parameter_source = 'NiPy'
    preproc.inputs.inputspec.realign_parameters = {"loops":[5],
                                                   "speedup":[5]}
    preproc.inputs.inputspec.do_whitening = False
    preproc.inputs.inputspec.timepoints_to_remove = 4
    preproc.inputs.inputspec.smooth_type = 'susan'
    preproc.inputs.inputspec.do_despike = False
    preproc.inputs.inputspec.surface_fwhm = 0.0
    preproc.inputs.inputspec.num_noise_components = 6
    preproc.inputs.inputspec.regress_before_PCA = False
    preproc.get_node('fwhm_input').iterables = ('fwhm', [0,5])
    preproc.get_node('take_mean_art').get_node('strict_artifact_detect').inputs.save_plot = True
    preproc.inputs.inputspec.ad_normthresh = 1
    preproc.inputs.inputspec.ad_zthresh = 3
    preproc.inputs.inputspec.do_slicetime = True
    preproc.inputs.inputspec.compcor_select = [True, True]
    preproc.inputs.inputspec.filter_type = 'fsl'
    preproc.get_node('bandpass_filter').iterables = [('highpass_freq',[0.01]),('lowpass_freq',[0.1])]
    preproc.inputs.inputspec.reg_params = [True, True, True, False, True, False]
    preproc.inputs.inputspec.fssubject_dir = freesurferdir
    #preproc.inputs.inputspec.tr = 1400/1000
    #preproc.inputs.inputspec.motion_correct_node = 'afni'
    #preproc.inputs.inputspec.sliceorder = slicetime_file
    #preproc.inputs.inputspec.sliceorder = list(np.linspace(0,1.4,64))

    def convert_units(tr):
        mstr = (tr*.001)
        return tr

    def get_sliceorder(in_file):
        import nipype.interfaces.dcmstack as dcm
        import numpy as np
        nii_wrp = dcm.NiftiWrapper.from_filename(in_file)
        sliceorder = np.argsort(np.argsort(nii_wrp.meta_ext.get_values('CsaImage.MosaicRefAcqTimes')[0])).tolist()
        return sliceorder

    wf.connect(tr_lookup, ("TR", convert_units), preproc, "inputspec.tr")
    wf.connect(stack, ('out_file', get_sliceorder), preproc, "inputspec.sliceorder")
    wf.connect(subject_id_infosource, 'subject_id', preproc, "inputspec.fssubject_id")
    wf.connect(datagrabber, "resting_nifti", preproc, "inputspec.func")

##Sampler##
    sampler = pe.Node(fs.SampleToSurface(), name='sampler')
    sampler.inputs.sampling_method = 'average'
    sampler.inputs.sampling_range = (0.2, 0.8, 0.1)
    sampler.inputs.sampling_units = 'frac'
    sampler.inputs.interp_method = 'nearest'
    sampler.inputs.out_type = 'nii'

    wf.connect(preproc, ('bandpass_filter.out_file',list_to_filename), sampler, 'source_file')
    wf.connect(preproc, ('getmask.register.out_reg_file',list_to_filename), sampler, 'reg_file')
    wf.connect(hemi_infosource, 'hemi', sampler, 'hemi')

##SXFM##
    sxfm = pe.Node(fs.SurfaceTransform(), name = 'sxfm')
    sxfm.inputs.target_subject = 'fsaverage4'
    sxfm.inputs.args = '--cortex --fwhm-src 5 --noreshape'
    sxfm.inputs.target_type = 'nii'
	
    wf.connect(sampler, 'out_file', sxfm, 'source_file')
    wf.connect(subject_id_infosource, 'subject_id', sxfm, 'source_subject')
    wf.connect(hemi_infosource, 'hemi', sxfm, 'hemi')
###########

    #report_wf = create_preproc_report_wf(os.path.join(preprocdir, "reports"))
    #report_wf.inputs.inputspec.fssubjects_dir = preproc.inputs.inputspec.fssubject_dir
    
    def pick_full_brain_ribbon(l):
        import os
        for path in l:
            if os.path.split(path)[1] == "ribbon.mgz":
                return path
            
    #wf.connect(preproc,"artifactdetect.plot_files", report_wf, "inputspec.art_detect_plot")
    #wf.connect(preproc,"take_mean_art.weighted_mean.mean_image", report_wf, "inputspec.mean_epi")
    #wf.connect(preproc,("getmask.register.out_reg_file", list_to_filename), report_wf, "inputspec.reg_file")
    #wf.connect(preproc,("getmask.fssource.ribbon",pick_full_brain_ribbon), report_wf, "inputspec.ribbon")
    #wf.connect(preproc,("CompCor.tsnr.tsnr_file", list_to_filename), report_wf, "inputspec.tsnr_file")
    #wf.connect(subject_id_infosource, 'subject_id', report_wf, "inputspec.subject_id")

##Datasink##
    ds = pe.Node(nio.DataSink(), name="datasink")
    ds.inputs.base_directory = os.path.join(preprocdir, "aimivolumes")
    wf.connect(preproc, 'bandpass_filter.out_file', ds, "preprocessed_resting")
    wf.connect(preproc, 'getmask.register.out_fsl_file', ds, "func2anat_transform")
    wf.connect(sampler, 'out_file', ds, 'sampledtosurf')
    wf.connect(sxfm, 'out_file', ds, 'sxfmout')
    #wf.write_graph()
    return wf

if __name__=='__main__':
    wf = get_wf()
    wf.run(plugin="CondorDAGMan", plugin_args={"template":"universe = vanilla\nnotification = Error\ngetenv = true\nrequest_memory=4000"})
    #wf.run(plugin="MultiProc", plugin_args={"n_procs":16})
    #wf.run(plugin="Linear", updatehash=True)
