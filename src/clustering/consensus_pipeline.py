import matplotlib
matplotlib.use('Agg')
import os
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio

from clustering.consensus import Consensus
from clustering.cluster import Cluster
from variables import subjects, sessions, workingdir, clusterdir, consensusdir, freesurferdir, consensus_dg_template, consensus_dg_args, hemispheres, similarity_types, cluster_types, n_clusters

def get_wf():
    wf = pe.Workflow(name="main_workflow")
    wf.base_dir = os.path.join(workingdir,"consensus_pipeline")
    wf.config['execution']['crashdump_dir'] = wf.base_dir + "/crash_files"

##Infosource##    
    #session_infosource = pe.Node(util.IdentityInterface(fields=['session']), name="session_infosource")
    #session_infosource.iterables = ('session', analysis_sessions)
    
    hemi_infosource = pe.Node(util.  IdentityInterface(fields=['hemi']), name="hemi_infosource")
    hemi_infosource.iterables = ('hemi', hemispheres)

    sim_infosource = pe.Node(util.IdentityInterface(fields=['sim']), name="sim_infosource")
    sim_infosource.iterables = ('sim', similarity_types)

    cluster_infosource = pe.Node(util.IdentityInterface(fields=['cluster']), name="cluster_infosource")
    cluster_infosource.iterables = ('cluster', cluster_types)

    n_clusters_infosource = pe.Node(util.IdentityInterface(fields=['n_clusters']), name="n_clusters_infosource")
    n_clusters_infosource.iterables = ('n_clusters', n_clusters)

##Datagrabber for subjects##
    dg_subjects = pe.Node(nio.DataGrabber(infields=['hemi', 'cluster', 'sim', 'n_clusters'], outfields=['all_subjects']), name="dg_subjects")
    datagrabber.inputs.base_directory = '/'
    datagrabber.inputs.template = '*'
    dg_subjects.inputs.template = consensus_dg_template
    dg_subjects.inputs.template_args = consensus_dg_args
    dg_subjects.inputs.sort_filelist = True

    #wf.connect(session_infosource, 'session', dg_subjects, 'session')
    wf.connect(hemi_infosource, 'hemi', dg_subjects, 'hemi')
    wf.connect(cluster_infosource, 'cluster', dg_subjects, 'cluster')
    wf.connect(sim_infosource, 'sim', dg_subjects, 'sim')
    wf.connect(n_clusters_infosource, 'n_clusters', dg_subjects, 'n_clusters')

##Consensus between subjects##
    intersubject = pe.Node(Consensus(), name = 'intersubject')
    wf.connect(dg_subjects, 'all_subjects', intersubject, 'in_Files')

    ##Cluster the Consensus Matrix##
    intersubject_cluster = pe.Node(Cluster(), name = 'intersubject_cluster')
    wf.connect(intersubject, 'consensus_mat', intersubject_cluster, 'in_File')
    wf.connect(hemi_infosource, 'hemi', intersubject_cluster, 'hemi')
    wf.connect(cluster_infosource, 'cluster', intersubject_cluster, 'cluster_type')
    wf.connect(n_clusters_infosource, 'n_clusters', intersubject_cluster, 'n_clusters')

##Datasink##
    ds = pe.Node(nio.DataSink(), name="datasink")
    ds.inputs.base_directory = consensusdir
    wf.connect(intersubject, 'out_File', ds, 'consensus_not_clustered')
    #wf.connect(intersession_cluster, 'out_File', ds, 'consensus_intersession')
    wf.connect(intersubject_cluster, 'out_File', ds, 'consensus_clustered')
    wf.write_graph()
    return wf

if __name__ == '__main__':
    wf = get_wf()               
    wf.run(plugin="CondorDAGMan", plugin_args={"template":"universe = vanilla\nnotification = Error\ngetenv = true\nrequest_memory=4000"})
    #wf.run(plugin="MultiProc", plugin_args={"n_procs":8})
