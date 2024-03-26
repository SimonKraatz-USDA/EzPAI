# EzPAI: Scripts for extracting Plant Area Index from zenith-looking Digital Camera Photography

## Background and need: 
EzPAI was developed to meet our need to monitor tree canopy changes with Digital Camera Photography (DCP). DCPs were installed 40+ USDA soil moisture monitoring stations, that were installed to help with calibration and validation efforts of NASA’s Soil Moisture Active Passive (SMAP) over forests [1]. This particular SMAP Validation Experiment extended from 2019 through 2022, but only few stations had a continuous 4 year record (most had 3 years). Originally the experiment plan was to be conducted and completed during 2019, however a combination of COVID and SMAP satellite dropouts caused delays in the ability to conduct the field campaign until 2022.

## Rationale on making this tool:
DCP were used instead of digital hemispherical photography (DHP), due to the much greater cost of DHP. Our DCPs were wildlife cameras that only cost about $100 each [2]. Thus, we were able to install them at nearly every soil moisture station. Our DCPs were set to take output JPG imagery at high resolution (2304 x 1728 pixels) every hour. Thus, data volume could exceed 10k photos per camera. 
Although [3] already reported on how to extract PAI from for DCP back in 2012, there were no free tools to extract PAI/LAI from DCP until about 2022. In 2022, a tool for doing this kind processing was released recently for the R programming language [4], but it did not appear in our literature search ahead of developing EzPAI. Hence, we developed our own tool which like [4] is also based on [3]. 
EzPAI only uses the OpenCV library in addition to other relatively basic python libraries such as numpy, imageio, pandas, matplotlib and scikit-image. One goal was to code as much as possible using numpy. This was to allow others to check/modify the scripts to their needs easily, and also to keep the overhead low for someone to transition this 'prototype' tool to other platforms such as into a C# application that can run on Windows. Currently we have no plans to do this, due to time constraints. Although Python is a slow programming language, we were still able to process all our camera data within reasonable effort/time using EzPAI.

## Running this tool
1. first install my environment: conda env create -f paiproc.yml
2. python 0_hourscreen.py -i MB520_2020-6-29_MillbrookSchool-a_testinput
3. python 1_blurscreen.py -i MB520_2020-6-29_MillbrookSchool-a_testinput
4. python 2_getPAI.py -i MB520_2020-6-29_MillbrookSchool-a_testinput
, where -i is the folder containing the jpg images. The tool should also work with any other image format compatible with the imageio library (not tested).

Explanation: 
0_hourscreen.py 
Example: python 0_hourscreen.py -i MB520_2020-6-29_MillbrookSchool-a_testinput
This script to filter camera imagery by time of day, and export valid data to a file named 0_hourscreen_<input folder name>.csv. The time stamp is set by the -c option, by default it is set to obtain from exif (-c 2) but create time and modified time can also be used. This tool accomplishes two goals: (1) it allows users to skip images that don't fall inside the hours of the day they're interested in; (2) it writes the image date and time into a csv alongside the image name and allows it to be adjusted from there. However, in practice we did not need this kind of screening, as the blur screening script and postprocess filtering described later usually take care of them. However, it is still needed, because the .csv output is a required input to 1_blurscreen.py. For the 21 images in the example, it took 1.2 seconds (Dell i5 Laptop).

1_blurscreen.py
Example: python 1_blurscreen.py -i MB520_2020-6-29_MillbrookSchool-a_testinput
This script is a second filter, and screens the images listed in 0_hourscreen_<input folder name>.csv for overly blurry images and writes them out to 1_blurscreen_<input folder name>.csv. Information and description of the default thresholds are provided in the script. The blur detection approach is based on the variance of Laplacian, i.e., if the variance (or max value) is lower than a threshold, the image is deemed blurry. For the 19 remaining images in 0_hourscreen csv it took 7.6 seconds (Dell i5 Laptop).

2_getPAI.py
Example: python 2_getPAI.py -i MB520_2020-6-29_MillbrookSchool-a_testinput
This script calculates all the items needed to obtain PAI, following the approach of Ryu et al. (2012). The output is given in 2_getPAI_<input folder name>.csv. Information on the default settings are available in the script. These settings were used over all our images, to get the initial results for PAI and other plant structural parameters. For the 17 remaining images in 1_blurscreeen csv it took 13.1 seconds (Dell i5 Laptop).

0_run_ctrl.py
Example: python 0_run_ctrl.py -i . -p MB

A convenience script for running the first three scripts in sequence using default values for each script, for each folder having a prefix (i.e., starting with the string) given by -p. Also, outputs duration of each step. 

- There could potentially be some value in skipping the blur detection, as it adds almost 50% processing time, and because many of the blurry imagery may also be filtered out in the postprocessing. But getPAI can be quickly changed to read in imagery from the hourscreen step output. 
- There can also be value in skipping hour screening, however given that it is fast and provides users with a csv of timestamps it not worth skipping. But one may want to modify the code to remove any screening and consider all available imagery, to avoid omitting useful data when the timestamps are wrong. Timestamps can be updated on the .csv as needed.
- It is recommended to update Timestamps ahead of the getPAI step, because timestamps are written out on the small overview images that summarize the PAI extraction process ('hist_' jpg), which can be useful for understanding or tweaking settings.

## Postprocessing, preliminary results, future work:
Full analysis/write-up regarding the PAI extraction using this tool is still in progress. But we plotted our EzPAI results after some basic QA checking not included with this tool, consisting of: (1) a re-screening data for blue sky index, high and low bin data which results in a data reduction; and (2) calibrating crown cover (CC) and crown porosity (CP) of cloud-free imagery to that of cloudy (blue sky index < cloudythr) imagery  using linear regression. This was done because we observed ‘jumps’ in same-day CC/CP/PAI values provided by EzPAI - these apparently were clearly related to cloudy vs clear-sky conditions. Such behavior is expected a priori, attributable to illumination differences. Ryu 2012 addressed this by changing thresholds for canopy/sky discrimination depending on whether the sky was cloudy or not. Although we also implemented this consideration using different values than Ryu 2012 (see our tmthri, tmthrc values in the script), we still observed a difference between cloudy and clear-sky CC/CP/PAI values. To save time, we decided to work with the data provided in the csv to calibrate the clear-sky CC & CP data to the cloudy CC & CP values and then re-calculated PAI. More details on the screening will be part of the upcoming publication on the SMAPVEX upward-looking camera analysis. After these steps, our results for PAI (the average of 2019-2022 average summer PAI values) were then compared to where LICOR-2200 in situ data were collected over 200 m x 200 m areas around the cameras in spring and summer 2022 (N=20) (see [5]). Results of this comparison show R = 0.89, RMSD = 0.93, MD = -0.54, and ubRMSD = 0.75, indicating good correspondence between this tool and the upward looking camera data processed by EzPAI. Other preliminary results also showed that postprocessed PAI results are temporally stable having within- and between-year variations of PAI (i.e., sdPAI/PAI) of < 5% at most stations. We're currently also working on converting our PAI values to LAI, and plan a detailed comparison between our dense time series to those obtained from remote sensing in the future.

## References:

[1] Colliander, A., Cosh, M. H., Kelly, V. R., Kraatz, S., Bourgeau-Chavez, L., Siqueira, P., ... & Yueh, S. H. (2020). SMAP detects soil moisture under temperate forest canopies. Geophysical research letters, 47(19), e2020GL089697.

[2] Moultrie WCT-00125 TimelapseCam. We are not 100% sure about the field of view on WCT-00125, it was not in the manual. The manual for WCT-00126 gives FOV as 40 degrees, which sounds about right for WCT-00125 also.

[3] Ryu, Y., Verfaillie, J., Macfarlane, C., Kobayashi, H., Sonnentag, O., Vargas, R., ... & Baldocchi, D. D. (2012). Continuous observation of tree leaf area index at ecosystem scale using upward-pointing digital cameras. Remote Sensing of Environment, 126, 116-125.

[4] Chianucci, F., Ferrara, C., & Puletti, N. (2022). coveR: an R package for processing digital cover photography images to retrieve forest canopy attributes. Trees, 36(6), 1933-1942.

[5] Cook, C. L. , Bourgeau-Chavez, L., Miller, M. E., Vander Bilt, D., Kraatz, S., Cosh, M.H., Colliander, A. 2024. Comparison of In Situ and Remotely Sensed Leaf Area Index of Northeastern American Deciduous, Mixed, and Coniferous Forests for SMAPVEX19-22. *In Review*.


