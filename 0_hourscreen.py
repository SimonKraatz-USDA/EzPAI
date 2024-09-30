#Research code by Simon Kraatz USDA (simon.kraatz@usda.gov)
#LAI, step 0: Purpose is to pre-screen upward looking camera data (JPG) by hour of the day, for making LAI estimates in later steps.

#DISCLAIMER: The USDA-ARS makes no warranties as to the merchantability or fitness of this research code for any particular purpose, or any other warranties expressed or implied. Since some portions of this code have been validated with only limited data sets, it should not be used to make operational management decisions. The USDA-ARS is not liable for any damages resulting from the use or misuse of this code its output and its accompanying documentation.

####-------------------HEADER-----------------####
import os, argparse
import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime, timedelta

####-------------------USER_SPECIFY-----------------####
mth_short = [10,11,12,1,2,3] #months with short sunhours
mth_med = [4,5,8,9] #month with normal sunhours
mth_long = [6,7] #months with most sunhours

ampm_tr1 = ['7:00', '12:00', '12:00', '18:00'] #['9:00','11:00','14:00','16:00'] #apr,may,aug,sep
ampm_tr2 = ['6:00', '12:00', '12:00', '19:00'] #['8:00','10:00','15:00','17:00'] #jun/jul
ampm_tr3 = ['8:00', '17:00'] #['10:00','15:00'] #oct/mar
ampm_tr4 = ['9:00', '16:00'] #['11:00','14:00'] #nov/feb

#concept is to screen by similar illumination condition. Sun won't rise as high in Oct-Feb, so estimating to be less intense/glare over noon, and not screening non-hours out. For other months, one can screen out by putting a time gap.

####-------------------FUNC/METH-----------------####
def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser( description='Screen JPG data by modify timestamp. Example: python 0_hourscreen4bad.py -i ./406cam/2022_31_ctimeok_imgshift2hr -f 0 -c 2')
    parser.add_argument('-i', '--indir', dest='indir', type=str, required=True,
                        help='The input directory where the .JPG are. Output is a .csv listing images passing the screen. Edit the .py to modify hours/month to consider.')
    parser.add_argument('-f', '--filthr', dest='filthr', type=int, required=False, default = 1,
                        help='Flag for filtering hour. Filtering == 1, see script. Else no filtering. Default = 1.')
    parser.add_argument('-c', '--c', dest='ctime', type=int, required=False, default = 2,
                        help='Flag for retrieving image create time. 0 = use os modified time. 1 = use os create time. 2 = use exif tag "DateTimeDigitized". Default = 2.')
    return parser.parse_args()

####-------------------PROGRAM-----------------####

def hourscreen(indir, filthr, ctime):
    '''
    Main process for pre-screening based on photo datetime
    '''
    # intialize variables based on directory and update cwd to indir
    outcsvn = '0_hourscreen_{0}.csv'.format(indir)
    fnl, timestampl = [], []
    cwd = os.getcwd()
    ind = os.path.join(cwd, indir)
    os.chdir(ind)

    # search for photos and pull timestamps
    jpgs = sorted([f for f in os.listdir('.') if f.endswith('.JPG') and not f.startswith('hist_')])
    for num, val in enumerate(jpgs):
        if ctime == 0:
            ut = os.path.getmtime(val) 
            aa = datetime.fromtimestamp(ut)
        elif ctime == 1:
            ut = os.path.getctime(val) 
            aa = datetime.fromtimestamp(ut)
        elif ctime == 2: 
            imginfo = Image.open(val)._getexif()
            aa = datetime.strptime(imginfo[36867], '%Y:%m:%d %H:%M:%S') 

        fnl.append(val)
        timestampl.append(aa)
    
    # create table with photo names and datetimes
    xx = pd.DataFrame(data = fnl, index = timestampl, columns =['file'])

    #filter data according to time periods
    if filthr == 1:
        #filter hours
        yy1_am = xx.between_time(ampm_tr1[0],ampm_tr1[1]).copy()  #apr,may,aug,sep
        yy2_am = xx.between_time(ampm_tr2[0],ampm_tr2[1]).copy()  #jun/jul

        yy1_pm = xx.between_time(ampm_tr1[2],ampm_tr1[3]).copy()  #apr,may,aug,sep
        yy2_pm = xx.between_time(ampm_tr2[2],ampm_tr2[3]).copy()  #jun/jul

        mix1 = xx.between_time(ampm_tr3[0],ampm_tr3[1]).copy()    #oct/mar
        mix2 = xx.between_time(ampm_tr4[0],ampm_tr4[1]).copy()    #nov/febi

        #then filter months
        yy1f_am = yy1_am[yy1_am.index.month.isin(mth_med)].copy()
        yy1f_pm = yy1_pm[yy1_pm.index.month.isin(mth_med)].copy()

        yy2f_am = yy2_am[yy2_am.index.month.isin(mth_long)].copy()
        yy2f_pm = yy2_pm[yy2_pm.index.month.isin(mth_long)].copy()

        mix1f = mix1[mix1.index.month.isin(mth_short)].copy()
        mix2f = mix2[mix2.index.month.isin(mth_short)].copy()

        #export
        zz = pd.concat([yy1f_am,yy1f_pm,yy2f_am,yy2f_pm,mix1f,mix2f])#, ignore_index=True)
    else:
        zz = xx 
    
    # clean up table and save to csv
    zz = zz.sort_index()
    zz = zz.drop_duplicates()
    zzl = zz['file'].to_list()
    zz.to_csv('0_hourscreen_{0}.csv'.format(indir))

if __name__ == '__main__':

    inps = cmdLineParse() # parse command line options
    hourscreen(inps.indir, inps.filthr, inps.ctime) # run main program
