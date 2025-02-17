"""
MODEL DRIVEN REGISTRATION for iBEAt study: quantitative renal MRI
@Kanishka Sharma 2021
Test script for T1 sequence using Model driven registration Library
"""
import sys
import glob
import os
import numpy as np
import itk
import SimpleITK as sitk
import pydicom
from pathlib import Path 
import time
from PIL import Image
import importlib
from MDR.MDR import model_driven_registration
from MDR.Tools import (read_DICOM_files, get_sitk_image_details_from_DICOM, 
                      sort_all_slice_files_acquisition_time, read_elastix_model_parameters,
                      export_images, export_maps)

np.set_printoptions(threshold=sys.maxsize)


def main():
    # selected sequence to process
    sequence = 'T1'
    # number of expected slices to process (example: iBEAt study number of slice = 5)
    slices = 5    

    # path definition  
    # your 'os.getcwd()' path should point to your local directory containing the  MDR-Library 
    # eg: /Users/kanishkasharma/Documents/GitHub/MDR_Library
    print(os.getcwd()) 

    DATA_PATH = os.getcwd() + r'/tests/test_data/DICOMs'
    OUTPUT_REG_PATH = os.getcwd() + r'/MDR_registration_output'
    Elastix_Parameter_file_PATH = os.getcwd() + r'/Elastix_Parameters_Files/iBEAt/BSplines_T1.txt' 
    output_dir =  OUTPUT_REG_PATH + '/T1/'

    # Organize files per each sequence:
    os.chdir(DATA_PATH)    
    # list all patient folders available to be processed
    patients_folders = os.listdir()
    # select patient folder to be processed from the list of available patient DICOMs supplied in patients_folders
    for patient_folder in patients_folders:
        if patient_folder not in ['test_case_iBEAt_4128009']: # eg: test case selected to be processed - change to your own test case
            continue
        # read path to the sequence to be processed for selected test patient case: eg: T1
        sequence_images_path = patient_folder + '/' + str(sequence) + '/DICOM'
        os.chdir(DATA_PATH + '/' + sequence_images_path)
        # read all dicom files for selected sequence
        dcm_files_found = glob.glob("*.dcm")
        if not dcm_files_found:
            dcm_files_found = glob.glob("*.IMA") # if sequence is IMA format instead of dcm
        # slice to be processed from selected sequence
        for slice in range(1, slices+1):
            current_slice = sequence + '_slice_' + str(slice)
            # single slice processing for T1 mapping sequence (here selected slice number is 3)
            if current_slice not in [sequence + '_slice_3']:
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
            # run T1 MDR test function
            iBEAt_test_T1(Elastix_Parameter_file_PATH, output_dir, ArrayDicomiBEAt, image_parameters, filenameDCM, lstFilesDCM)

                    
def iBEAt_test_T1(Elastix_Parameter_file_PATH, output_dir, ArrayDicomiBEAt, image_parameters, filenameDCM, lstFilesDCM):
    """ Example application of MDR in renal T1 mapping (iBEAt data).
    
    Args
    ----
    Elastix_Parameter_file_PATH (string): complete path to the Elastix parameter file to be used
    output_dir (string): directory where results are saved
    ArrayDicomiBEAt (numpy.ndarray): input DICOM to numpy array (unsorted)
    image_parameters (sitk tuple):  image spacing
    filenameDCM (pathlib.PosixPath): dicom filenames to process
    lstFilesDCM (list): list of  dicom files to process

    Description
    -----------
    This function performs model driven registration for selected T1 sequence on a single selected slice 
    and returns as output the MDR registered images, signal model fit, deformation field x, deformation field y, 
    fitted parameters S0 and T1 map, and the final diagnostics.
    """

    start_computation_time = time.time()
    # define numpy array with same input shape as original DICOMs
    image_shape = np.shape(ArrayDicomiBEAt)
    original_images = np.zeros(image_shape)

    # read signal model parameters and slice sorted per T1 inversion time
    full_module_name = "models.iBEAt_T1"
    signal_model_parameters, slice_sorted_inv_time = read_signal_model_parameters(full_module_name,filenameDCM, lstFilesDCM)

    # initialise original_images with sorted images per T1 inversion times to run MDR
    for i, s in enumerate(slice_sorted_inv_time):
        img2d = s.pixel_array
        original_images[:, :, i] = img2d
    
    # read signal model parameters
    elastix_model_parameters = read_elastix_model_parameters(Elastix_Parameter_file_PATH, ['MaximumNumberOfIterations', 256])
    
    #Perform MDR
    MDR_output = model_driven_registration(original_images, image_parameters, signal_model_parameters, elastix_model_parameters, precision = 1)
    # #Export results
    export_images(MDR_output[0], output_dir +'/coregistered/MDR-registered_T1_')
    export_images(MDR_output[1], output_dir +'/fit/fit_image_')
    export_images(MDR_output[2][:,:,0,:], output_dir +'/deformation_field/final_deformation_x_')
    export_images(MDR_output[2][:,:,1,:], output_dir +'/deformation_field/final_deformation_y_')
    export_maps(MDR_output[3][::2], output_dir + '/fitted_parameters/S0', np.shape(original_images))
    export_maps(MDR_output[3][1::2], output_dir + '/fitted_parameters/T1Map', np.shape(original_images))
    MDR_output[4].to_csv(output_dir + 'T1_largest_deformations.csv')

    # Report computation times
    end_computation_time = time.time()
    print("total computation time for MDR (minutes taken:)...")
    print(0.0166667*(end_computation_time - start_computation_time)) # in minutes
    print("completed MDR registration!")
    print("Finished processing Model Driven Registration case for iBEAt study T1 sequence!")

 
 # read sequence acquisition parameter for signal modelling
 # sort slices according to T1 inversion times
def read_signal_model_parameters(full_module_name,filenameDCM, lstFilesDCM):

    # select model
    MODEL = importlib.import_module(full_module_name)
    inversion_times, slice_sorted_inv_time = MODEL.read_inversion_times_and_sort(filenameDCM, lstFilesDCM)
    # select signal model paramters
    signal_model_parameters = [MODEL, inversion_times]

    return signal_model_parameters, slice_sorted_inv_time
