import sys
import os
import glob
import numpy as np
import nibabel as nib
from sklearn.linear_model import LinearRegression
import warnings

warnings.simplefilter('ignore')

subject = sys.argv[1]
funcDir = sys.argv[2]
labelDir = sys.argv[3]
parcDir = sys.argv[4]
volmDir = sys.argv[5]

# check if surface directory exist; exit if false
if os.listdir(funcDir+'/surfaces/'):
    print('')
    print('-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-')
    print('surfaces directory found; lets get the party started!')
    print('-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-')
    print('')
else:
    print('')
    print(':( sad face :( sad face :( sad face :(')
    print('No surface directory. Exiting. Bye-bye')
    print(':( sad face :( sad face :( sad face :(')
    print('')
    exit()


# ------------------------------------------
# Conte69 processing
# ------------------------------------------

# Find and load surface-registered ctx + sctx + cerebellum timeseries
os.chdir(funcDir+'/surfaces/')
x_lh = " ".join(glob.glob(funcDir+'/surfaces/'+'*lh*c69-32k_10mm*'))
x_rh = " ".join(glob.glob(funcDir+'/surfaces/'+'*rh*c69-32k_10mm*'))
lh_data = nib.load(x_lh)
lh_data = np.squeeze(lh_data.get_fdata())
rh_data = nib.load(x_rh)
rh_data = np.squeeze(rh_data.get_fdata())

# exit if more than one scan exists
if len(x_lh.split(" ")) == 1:
    print('')
    print('-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-')
    print('only one scan found; all good in the hood')
    print('-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-')
    print('')
else:
    print('more than one scan found; exiting. Bye-bye')
    exit()

# Reformat data
data = []
data = np.transpose(np.append(lh_data, rh_data, axis=0))
n_vertex_ctx_c69 = data.shape[1]
del lh_data
del rh_data

# Load subcortical and cerebellar timeseries
# Subcortex
sctx = np.loadtxt(funcDir+'/volumetric/'+subject+'_singleecho_timeseries_subcortical.txt')
n_sctx = sctx.shape[1]

# Cerebellum
# A little hacky because the co-registration to fMRI space make some cerebellar ROIs disappear
# Missing label indices are replaced by zeros in timeseries and FC matrix
cereb_tmp = np.loadtxt(funcDir+'/volumetric/'+subject+'_singleecho_timeseries_cerebellum.txt')
f = open(funcDir+'/volumetric/'+subject+'_singleecho_fmrispace_cerebellum_roi_stats.txt', "rt")
cerebLabels = f.read()
s1 = cerebLabels.find("nii.gz")
startROIs = s1 + len("nii.gz") + 6
values = cerebLabels[startROIs:].split("\t")
roiLabels = values[0::2]

def missing_elements(roiList):
    start, end = 0, 33
    return sorted(set(range(start, end + 1)).difference(roiList))

if len(roiLabels) == 34: # no labels disappeared in the co-registration
    print('All cerebellar labels found in parcellation!')
    cereb = cereb_tmp
    exclude_labels = [np.nan]
else:
    print('Some cerebellar ROIs were lost in co-registration to fMRI space')
    cereb = np.zeros((cereb_tmp.shape[0], 34), dtype=np.int8)
    roiLabelsInt = np.zeros((1,len(roiLabels)), dtype=np.int8)
    for ii in range(len(roiLabels)):
        roiLabelsInt[0,ii] = int(float(roiLabels[ii]))
    roiLabelsInt = roiLabelsInt - 1
    for ii in range(len(roiLabels)):
        cereb[:,roiLabelsInt[0,ii]] = cereb_tmp[:,ii]
    exclude_labels = missing_elements(roiLabelsInt[0])
    print('Matrix entries for following ROIs will be zero: ', exclude_labels)

# Calculate number of non cortical rows/colunms in matrix and concatenate
n = sctx.shape[1] + cereb.shape[1] # so we know data.shape[1] - n = num of ctx vertices only
data = np.append(np.append(sctx, cereb, axis=1), data, axis=1)

# Load confound files
spike = []
os.chdir(funcDir+'/volumetric/')
x_spike = " ".join(glob.glob(funcDir+'/volumetric/'+'*spikeRegressors_FD*'))
x_dof = " ".join(glob.glob(funcDir+'/volumetric/'+'*singleecho.1D'))
x_refrms = " ".join(glob.glob(funcDir+'/volumetric/'+'*metric_REFRMS.1D'))
x_fd = " ".join(glob.glob(funcDir+'/volumetric/'+'*metric_FD*'))
if x_spike:
    spike = np.loadtxt(x_spike)
    if spike.ndim == 1:
        spike = np.expand_dims(spike, axis=1)
    else:
        print("spike file loaded as 2D")
    # regress out spikes from individual timeseries
    ones = np.ones((spike.shape[0], 1))
    mdl = []
    mdl = np.append(ones, spike, axis=1)
    # conte
    slm = LinearRegression().fit(data, mdl)
    data_corr = data-np.dot(mdl, slm.coef_)
else:
    del spike
    print('no spikey, no spikey, will skippy')
    data_corr = data

# save spike regressed and concatenanted timeseries (subcortex, cerebellum, cortex)
np.savetxt(funcDir+'/surfaces/' + subject + '_rsfMRI-timeseries_conte69_clean.txt', data_corr, fmt='%.6f')

# Read the processed parcellations
parcellationList = os.listdir(volmDir)

# Slice the file names and remove nii*
parcellationList=[sub.split('nativepro_')[1].split('.nii')[0] for sub in parcellationList]

# Remove cerebellum and subcortical strings
parcellationList.remove('subcortical')
parcellationList.remove("cerebellum")

# Start with conte parcellations
parcellationList_conte=[sub + '_conte69' for sub in parcellationList]

for parcellation in parcellationList_conte:
    parcPath = os.path.join(parcDir, parcellation) + '.csv'
    
    if parcellation == "aparc-a2009s_conte69":
        print("parcellation " + parcellation + " currently not supported")
        continue
    else:
        thisparc = np.loadtxt(parcPath)

    # Parcellate cortical timeseries
    data_corr_ctx = data_corr[:, -n_vertex_ctx_c69:]
    uparcel = np.unique(thisparc)
    ts_ctx = np.zeros([data_corr_ctx.shape[0], len(uparcel)])
    for lab in range(len(uparcel)):
        tmpData = data_corr_ctx[:, thisparc == lab]
        ts_ctx[:,lab] = np.mean(tmpData, axis = 1)

    ts = np.append(data_corr[:, :n], ts_ctx, axis=1)
    ts_r = np.corrcoef(np.transpose(ts))

    if np.isnan(exclude_labels[0]) == False:
        for i in exclude_labels:
            ts_r[:, i + n_sctx] = 0
            ts_r[i + n_sctx, :] = 0
        ts_r = np.triu(ts_r)
    else:
        ts_r = np.triu(ts_r)

    np.savetxt(funcDir + '/surfaces/' + subject + '_rsfMRI-connectome_' + parcellation + '_clean.txt',
               ts_r, fmt='%.6f')

# Clean up
del ts_r
del ts
del data_corr
del data
del thisparc


# ------------------------------------------
# Native surface processing
# ------------------------------------------

# Process left hemisphere timeseries
os.chdir(funcDir+'/surfaces/')
x_lh_nat = " ".join(glob.glob(funcDir+'/surfaces/'+'*fmri2fs_lh_10mm.mgh'))
lh_data_nat = nib.load(x_lh_nat)
lh_data_nat = np.transpose(np.squeeze(lh_data_nat.get_fdata()))

spike = []
if x_spike:
    spike = np.loadtxt(x_spike)
    if spike.ndim == 1:
        spike = np.expand_dims(spike, axis=1)
    else:
        print("spike file loaded as 2D")
    # regress out spikes from individual timeseries
    ones = np.ones((spike.shape[0], 1))
    mdl = []
    mdl = np.append(ones, spike, axis=1)
    slm = LinearRegression().fit(lh_data_nat, mdl)
    lh_data_nat_corr = lh_data_nat-np.dot(mdl, slm.coef_)
    del lh_data_nat
    del slm
else:
    del spike
    print('no spikey, no spikey, will skippy')
    lh_data_nat_corr = lh_data_nat
    del lh_data_nat

# Process right hemisphere timeseries
os.chdir(funcDir+'/surfaces/')
x_rh_nat = " ".join(glob.glob(funcDir+'/surfaces/'+'*fmri2fs_rh_10mm.mgh'))
rh_data_nat = nib.load(x_rh_nat)
rh_data_nat = np.transpose(np.squeeze(rh_data_nat.get_fdata()))

spike = []
if x_spike:
    spike = np.loadtxt(x_spike)
    if spike.ndim == 1:
        spike = np.expand_dims(spike, axis=1)
    else:
        print("spike file loaded as 2D")
    # regress out spikes from individual timeseries
    ones = np.ones((spike.shape[0], 1))
    mdl = []
    mdl = np.append(ones, spike, axis=1)
    slm = LinearRegression().fit(rh_data_nat, mdl)
    rh_data_nat_corr = rh_data_nat-np.dot(mdl, slm.coef_)
    del rh_data_nat
    del slm
else:
    del spike
    print('no spikey, no spikey, will skippy')
    rh_data_nat_corr = rh_data_nat
    del rh_data_nat

# Concatenate hemispheres and clean up
dataNative_corr = np.append(lh_data_nat_corr, rh_data_nat_corr, axis=1)
del lh_data_nat_corr
del rh_data_nat_corr

# Process subcortex and cerebellum
spike = []
if x_spike:
    spike = np.loadtxt(x_spike)
    if spike.ndim == 1:
        spike = np.expand_dims(spike, axis=1)
    else:
        print("spike file loaded as 2D")
    # regress out spikes from individual timeseries
    ones = np.ones((spike.shape[0], 1))
    mdl = []
    mdl = np.append(ones, spike, axis=1)
    # Subcortex
    slm = LinearRegression().fit(sctx, mdl)
    sctx_corr = sctx-np.dot(mdl, slm.coef_)
    del sctx 
    # Cerebellum
    slm = LinearRegression().fit(cereb, mdl)
    cereb_corr = cereb-np.dot(mdl, slm.coef_)
    del cereb
else:
    del spike
    print('no spikey, no spikey, will skippy')
    # Subcortex
    sctx_corr = sctx
    del sctx
    # Cerebellum
    cereb_corr = cereb
    del cereb

# Generate native surface connectomes
for parcellation in parcellationList:

    # Load left and right annot files
    fname_lh = 'lh.' + parcellation + '_mics.annot'
    ipth_lh = os.path.join(labelDir, fname_lh)
    [labels_lh, ctab_lh, names_lh] = nib.freesurfer.io.read_annot(ipth_lh, orig_ids=True)
    fname_rh = 'rh.' + parcellation + '_mics.annot'
    ipth_rh = os.path.join(labelDir, fname_rh)
    [labels_rh, ctab_rh, names_rh] = nib.freesurfer.io.read_annot(ipth_rh, orig_ids=True)
    # Join hemispheres
    nativeLength = len(labels_lh)+len(labels_rh)
    native_parc = np.zeros((nativeLength))
    for x in range(len(labels_lh)):
        native_parc[x] = np.where(ctab_lh[:,4] == labels_lh[x])[0][0]
    for x in range(len(labels_rh)):
        native_parc[x + len(labels_lh)] = np.where(ctab_rh[:,4] == labels_rh[x])[0][0] + len(ctab_lh)

    # Generate connectome on native space parcellation
    # Parcellate cortical timeseries
    uparcel = np.unique(native_parc)
    ts_native_ctx = np.zeros([dataNative_corr.shape[0], len(uparcel)])
    for lab in range(len(uparcel)):
        tmpData = dataNative_corr[:, native_parc == int(uparcel[lab])]
        ts_native_ctx[:,lab] = np.mean(tmpData, axis = 1)
    
    ts = np.append(np.append(sctx_corr, cereb_corr, axis=1), ts_native_ctx, axis=1)
    np.savetxt(funcDir + '/surfaces/' + subject + '_rsfMRI-timeseries_' + parcellation + '_clean.txt', ts, fmt='%.12f')
    
    ts_r = np.corrcoef(np.transpose(ts))
        
    if np.isnan(exclude_labels[0]) == False:
        for i in exclude_labels:
            ts_r[:, i + n_sctx] = 0
            ts_r[i + n_sctx, :] = 0
        ts_r = np.triu(ts_r)    
    else:
        ts_r = np.triu(ts_r)
        
    np.savetxt(funcDir + '/surfaces/' + subject + '_rsfMRI-connectome_' + parcellation + '_clean.txt', ts_r, fmt='%.6f')

# Clean up
del ts_native_ctx
del native_parc
del ts_r
del ts
del dataNative_corr
del sctx_corr
del cereb_corr

# ------------------------------------------
# Additional QC
# ------------------------------------------

# mean framewise displacement + save plot
fd = np.loadtxt(x_fd)
title = 'mean FD: ' + str(np.mean(fd))
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(16, 6))
plt.plot(fd, color="#2171b5")
plt.title(title, fontsize=16)
ax.set(xlabel='')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.savefig(funcDir+'/surfaces/' + subject + '_rsfMRI-framewiseDisplacement.png', dpi=300)

del fd

# tSNR
lh_nat_noHP = " ".join(glob.glob(funcDir+'/surfaces/'+'*fmri2fs_lh_NoHP.mgh'))
lh_nat_noHP_data = nib.load(lh_nat_noHP)
lh_nat_noHP_data = np.squeeze(lh_nat_noHP_data.get_fdata())
rh_nat_noHP = " ".join(glob.glob(funcDir+'/surfaces/'+'*fmri2fs_rh_NoHP.mgh'))
rh_nat_noHP_data = nib.load(rh_nat_noHP)
rh_nat_noHP_data = np.squeeze(rh_nat_noHP_data.get_fdata())

lhM = np.mean(lh_nat_noHP_data, axis = 1)
lhSD = np.std(lh_nat_noHP_data, axis = 1)
lh_tSNR = np.divide(lhM, lhSD)

rhM = np.mean(rh_nat_noHP_data, axis = 1)
rhSD = np.std(rh_nat_noHP_data, axis = 1)
rh_tSNR = np.divide(rhM, rhSD)

tSNR = np.append(lh_tSNR, rh_tSNR)
tSNR = np.expand_dims(tSNR, axis=1)

np.savetxt(funcDir+'/surfaces/' + subject + '_tSNR.txt', tSNR, fmt='%.12f')
