"""
MODEL DRIVEN REGISTRATION for iBEAt study: quantitative renal MRI
@Kanishka Sharma 2021
Test script for DWI sequence using Model driven registration Library
"""
import sys
import glob
import os
import numpy as np
import itk
import SimpleITK as sitk
import pydicom
from pathlib import Path 
import importlib
import time
from PIL import Image
from MDR.MDR import model_driven_registration  
from MDR.Tools import (read_DICOM_files, get_sitk_image_details_from_DICOM, 
                      sort_all_slice_files_acquisition_time, read_elastix_model_parameters,
                      export_images, export_maps)


np.set_printoptions(threshold=sys.maxsize)

def main():
    # selected sequence to process
    sequence = 'IVIM'
    # number of expected slices to process (example: iBEAt study number of slice = 30)
    slices = 30    

    # path definition  
    # your 'os.getcwd()' path should point to your local directory containing the  MDR-Library 
    # eg: /Users/kanishkasharma/Documents/GitHub/MDR_Library
    print(os.getcwd()) 

    DATA_PATH = os.getcwd() + r'/tests/test_data/DICOMs'
    OUTPUT_REG_PATH = os.getcwd() + r'/MDR_registration_output'
    Elastix_Parameter_file_PATH = os.getcwd() + r'/Elastix_Parameters_Files/iBEAt/BSplines_IVIM.txt' 
    output_dir =  OUTPUT_REG_PATH + '/DWI/'

    # Organize files per each sequence:
    os.chdir(DATA_PATH)    
    # list all patient folders available to be processed
    patients_folders = os.listdir()
    # select patient folder to be processed from the list of available patient DICOMs supplied in patients_folders
    for patient_folder in patients_folders:
        if patient_folder not in ['test_case_iBEAt_4128009']: # eg: test case selected to be processed - change to your own test case
            continue
        # read path to the sequence to be processed for selected test patient case: eg: DWI
        sequence_images_path = patient_folder + '/' + str(sequence) + '/DICOM'
        os.chdir(DATA_PATH + '/' + sequence_images_path)
        # read all dicom files for selected sequence
        dcm_files_found = glob.glob("*.dcm")
        if not dcm_files_found:
            dcm_files_found = glob.glob("*.IMA") # if sequence is IMA format instead of dcm
        # slice to be processed from selected sequence
        for slice in range(1, slices+1):
            current_slice = sequence + '_slice_' + str(slice)
            # single slice processing for DWI sequence (here selected slice number is 15)
            if current_slice not in [sequence + '_slice_15']:
                continue
            # read slice path to be processed
            slice_path = DATA_PATH + '/' + sequence_images_path + '/' + current_slice
            data = Path(slice_path)
            # list of all DICOMs to be processed for the selected slice (example: slice number = 15 here)
            lstFilesDCM = list(data.glob('**/*.IMA')) 
    
            # read all dicom files for the selected sequence and slice
            files, ArrayDicomiBEAt, filenameDCM = read_DICOM_files(lstFilesDCM)
            # get sitk image parameters for registration (origin and spacing)
            image_parameters = get_sitk_image_details_from_DICOM(slice_path)
            # sort slices correctly - based on acquisition time for model driven registration
            sorted_slice_files = sort_all_slice_files_acquisition_time(files)
            # run DWI MDR test 
            iBEAt_test_DWI(Elastix_Parameter_file_PATH, output_dir, sorted_slice_files, ArrayDicomiBEAt, image_parameters, filenameDCM, lstFilesDCM)


# test DWI using model driven registration
def iBEAt_test_DWI(Elastix_Parameter_file_PATH, output_dir, sorted_slice_files, ArrayDicomiBEAt, image_parameters, filenameDCM, lstFilesDCM):
    """ Example application of MDR in renal DWI (iBEAt data).
    
    Args
    ----
    Elastix_Parameter_file_PATH (string): complete path to the elastix parameter file to be used
    output_dir (string): directory where results are saved
    slice_sorted_files (list): selected slices to process using MDR: sorted according to acquisition time 
    ArrayDicomiBEAt (numpy.ndarray): input DICOM to numpy array (unsorted)
    image_parameters (SITK input): image spacing
    filenameDCM (pathlib.PosixPath): dicom filenames to process
    lstFilesDCM (list): list of dicom files to process

    Description
    -----------
    This function performs model driven registration for selected DWI sequence on a single selected slice 
    and returns as output the MDR registered images, signal model fit, deformation field x, deformation field y, 
    fitted parameters S0 and ADC, and the final diagnostics.
    """
    start_computation_time = time.time()
    # define numpy array with same input shape as original DICOMs
    image_shape = np.shape(ArrayDicomiBEAt)
    original_images = np.zeros(image_shape)

    # initialise original_images with sorted acquisiton times to run MDR
    for i, s in enumerate(sorted_slice_files):
        img2d = s.pixel_array
        original_images[:, :, i] = img2d

    # read signal model parameters
    full_module_name = "models.iBEAt_DWI_monoexponential"
    signal_model_parameters = read_signal_model_parameters(full_module_name, filenameDCM, lstFilesDCM)
    # read signal model parameters
    elastix_model_parameters = read_elastix_model_parameters(Elastix_Parameter_file_PATH, ['MaximumNumberOfIterations', 256])
    
    #Perform MDR
    MDR_output = model_driven_registration(original_images, image_parameters, signal_model_parameters, elastix_model_parameters, precision = 1)

    #Export results
    export_images(MDR_output[0], output_dir +'/coregistered/MDR-registered_DWI_')
    export_images(MDR_output[1], output_dir +'/fit/fit_image_')
    export_images(MDR_output[2][:,:,0,:], output_dir +'/deformation_field/final_deformation_x_')
    export_images(MDR_output[2][:,:,1,:], output_dir +'/deformation_field/final_deformation_y_')
    export_maps(MDR_output[3][::2], output_dir + '/fitted_parameters/S0', np.shape(original_images))
    export_maps(MDR_output[3][1::2], output_dir + '/fitted_parameters/ADC', np.shape(original_images))
    MDR_output[4].to_csv(output_dir + 'DWI_largest_deformations.csv')

    # Report computation times
    end_computation_time = time.time()
    print("total computation time for MDR (minutes taken:)...")
    print(0.0166667*(end_computation_time - start_computation_time)) # in minutes
    print("completed MDR registration!")
    print("Finished processing Model Driven Registration case for iBEAt study DWI sequence!")


## read sequence acquisition parameter for signal modelling
def read_signal_model_parameters(full_module_name, filenameDCM, lstFilesDCM):

    # generate a module named as a string
    MODEL = importlib.import_module(full_module_name)
    b_values, bVec_original, image_orientation_patient, slice_sorted_b_values  = MODEL.read_dicom_tags_IVIM(filenameDCM, lstFilesDCM)
    # select signal model paramters
    signal_model_parameters = [MODEL]
    signal_model_parameters.append([b_values, bVec_original, image_orientation_patient])
    
    return signal_model_parameters
