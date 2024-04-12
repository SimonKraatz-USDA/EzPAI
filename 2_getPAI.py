#Research code by Simon Kraatz USDA (simon.kraatz@usda.gov)
#LAI, step 2: This script will estimate Plant Area Index similar as done in Ryu 2012 paper: Continuous observation of tree leaf area index at ecosystem scale using upward-pointing digital cameras. 
#Major difference is in how we identify large gaps. We use contours, and screen according to contour size. We qualitatively determined fcval = 10000 to be give reasonable results ahead of checking the % screened
#We later implemented to check for the minimum pixel area classified as large gap, the column minpixarea in the output:
#for our imagery, using fcval = 10000, minpixarea ~ 0.3% (this is what we used). fcval = 50k, minpixarea ~ 1.4%. fcval = 100k, minpixarea ~ 3%.

#DISCLAIMER: The USDA-ARS makes no warranties as to the merchantability or fitness of this research code for any particular purpose, or any other warranties expressed or implied. Since some portions of this code have been validated with only limited data sets, it should not be used to make operational management decisions. The USDA-ARS is not liable for any damages resulting from the use or misuse of this code its output and its accompanying documentation.

####-------------------HEADER-----------------####
import os, argparse, cv2
import imageio.v2 as imageio
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from skimage.util import img_as_ubyte
from numpy import linalg as LA

####-------------------USER_SPECIFY-----------------####
cloudythr = 0.54 #qualitatively estimated at 401 to be give reasonable results for the Wingscapes TimelapseCam WCT-00125
k = 0.65 #This is needed to set a value for Plant Area Index (PAI). Depends on G function and camera field of view. We calculated from G(40)/cos(40) using the G function for 'erectophile' plotted in Ryu 2012. Our camera FOV estimated to be 40 degrees. 
skipbotpix = 100 #the ~100 pixels at the bottom contain the camera info display, we want to remove them ahead of processing

####-------------------'CONSTANTS'-----------------####
#can modify, but recommended not to
dpi = 70 #if image of classification process is output, make them smaller dpi for space/speed consideration
counts_med_mult = 0.5 #allows for peaks that are smaller than the median ... helps obtain better rosin bin numbers. Same idea as suggested in McFarlane 2011.
binsz = 4 #use bin intervals of 4 DN, convenient for the 256 unit8 image data. 
lbinskip = 2 #skip first X bins to omit very low DN values during search for Rosin bins. This can/should probably be set much more aggressively to ~10 for a priori screening, but we use a generous threshold first, because it can be revised as needed during postprocessing the csv data (much faster!)
rbinskip = 62 #skip bins after X to omit very high DN values during search for Rosin bins. Same idea as above, could be much smaller than 62.
stride = 5 #for binsz=4, lbinskip=2, rbinskip=62 there are 60 bins between. Stride 5 searches 5 bins at a time, 12 times.
div = 1 #for sliding window with overlap for larger stides (values other than 1 were only tested early in development, they could throw an error now)

#tmthri, tmthrc are canopy vs sky thresholds. smaller means more sky. Common values are 0.25, 0.50 and 0.75. Richardson paper.
tmthri = 0.25 #use if clear sky, i.e., blue sky index value >= 0.54. This is a weight for identifying the plant/sky cutoff bin - the bin where above which there is sky/cloud DNs. Ryu 2012 used 0.75, but 0.50 seems to perform better for what we have (401 cam, qualitative)
tmthrc = 0.25 #use if overcast sky. Ryu 2012 uses 0.5, but 0.25 appears more suitable according to our 401 cam data (qualitative)
skythr = 0.75 #this is only for calculating the blue sky index, to identify sky pixels in a strict manner (i.e., skythr = 0.75). Then, if cloudy, the sky/canopy threshold is informed by tmthrc, otherwise tmthri is used. (qualitative)
bins_in = np.arange(0,257,binsz) #bin edge counts, a greater number than the histogram bins
fcval = 10000 #this is the threshold for filtering out find contours, only use larger ones than this number. It is is only indirectly related to pixel count, 10k seems to be close to > 1.3% image pixels for our 2304 x (1728-skipbotpix) images. Should be scaled in line with total pixel count.

####-------------------FUNC/METH-----------------####
def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser( description='Screen JPG data by modify timestamp. Example: python 0_hourscreen.py -i 401cam')
    parser.add_argument('-i', '--indir', dest='indir', type=str, required=True,
                        help='The input directory where the .JPG and .csv of step 1 are. Output is a .csv listing images passing the screen.')
    return parser.parse_args()

####-------------------PROGRAM-----------------####
def get_PAI(indir):
    '''
    Main process for retrieving PAI (inclusive of all plant matter not just leaves).
    '''
    # intialize variables based on directory and update cwd to indir
    cwd = os.getcwd()
    ind = os.path.join(cwd, indir)
    os.chdir(ind)
    
    #read output from step 1 (1_blurscreen.py)
    if os.path.exists(os.path.join(cwd,indir,csvout)) == False:
        fin = [f for f in os.listdir('.') if f.startswith('1_blurscreen') and f.endswith('.csv')][0]
    
    # import list of photos (generated by 1_blurscreen)    
    xx = pd.read_csv(fin, index_col=0, parse_dates=True)
    
    # did xx.index import as an object instead of a datetime?
    # xx.index = pd.to_datetime(xx.index, format = '%Y-%m-%d %H:%M:%S')
    # xx.index = pd.to_datetime(xx.index, format = '%Y-%m-%d %H:%M:%S.%f')
    # xx.index = pd.to_datetime(xx.index, format = '%m/%d/%Y %H:%M')
    
    # initialize variables needed for processing
    inf = xx['file'].to_list()
    infn = len(inf)
    correctdt = xx.index.tolist() 
    dt, fn, leftmaxbin, leftmaxcount, rightmaxbin, rightmaxcount, lucl, rucl, skyidxl, gfl, minpixareal, ccl, cpl, pail = [], [], [], [], [], [], [], [], [], [], [], [], [], []
    
    # retrieve PAI for each photo
    for num, val in enumerate(inf):
        print('Working on file {0}, {1} out of {2}'.format(val, num+1, infn))
        
        # reset thr to user-defined value and progress to next image
        tmthr = tmthri
        bb = correctdt[num]
        
        # load image bands and truncate bottom text if necessary
        arr0 = imageio.imread(val)
        arr1 = arr0[:-skipbotpix,:].copy() #truncates the nonimg part, copy in case operations modify the array.
        # arr1 = rescale(arr1,0.5,multichannel=True) # downscale if needed for speed
        arr = img_as_ubyte(arr1)
        
        # bin based on blue band
        counts, bins = np.histogram(arr[:,:,2], bins=bins_in) #only use blue channel
        latmpt, ratmpt = 1, 1 #count refer to how many windows slided
        lmaxfound, rmaxfound = 0, 0 #flag, 0 meaning max had not been found. One for each of the two expected peaks in histogram (canopy on low end, sky on high end)
        counts_med = np.median(counts)
        counts_max = np.max(counts)
    
    
    # while loops to find local max(s)
    # there is probably an elegant way to combine the two while loops into one, or express in a function, but for debug easier to separate them
        
        # fromleft:
        while lbinskip+stride*(latmpt-1) < rbinskip and lmaxfound == 0:
            a = lbinskip+stride*(latmpt-1)//div #start window
            b = a+stride                        #end window
            lmax_idx = counts[a:b].argmax()
            if (lmax_idx != stride-1) & (counts[lmax_idx+a] > counts_med*counts_med_mult):# (lmax_idx != 0)
                lmaxfound = 1
                break
            latmpt = latmpt + 1
        
        # fromright
        while rbinskip-stride*ratmpt > lbinskip and rmaxfound == 0:
            c = rbinskip-stride*ratmpt//div     #start window
            d = c+stride                        #end window
            rmax_idx = counts[c:d].argmax()
            if (rmax_idx !=0) & (counts[rmax_idx+c]>counts_med*counts_med_mult): #(rmax_idx != stride-1) #stride-rmax_idx < stride-2:# and rmax_idx > 2: #maybe from right doesnt need?
                rmaxfound = 1
                break
            ratmpt = ratmpt + 1
        
        # report values corresponding to max_idcx 
        lmxb = bins[lmax_idx+a]
        lmxc = counts[lmax_idx+a]
        rmxb = bins[rmax_idx+c]
        rmxc = counts[rmax_idx+c]
        
        print('left localmax is in stride relative bin number %s, bin value %s, count %s' %(lmax_idx, lmxb, lmxc))
        print('right localmax is in stride relative bin number %s, bin value %s, count %s' %(rmax_idx, rmxb, rmxc))
        
        # append values to larger lists
        dt.append(bb)
        fn.append(val)
        leftmaxbin.append(lmxb)
        leftmaxcount.append(lmxc)
        rightmaxbin.append(rmxb)
        rightmaxcount.append(rmxc)
            
    #if left == right; unimodal ~no leaves
    #ROSIN thresholding  ............. this might also work as a separate function
        aa = np.where(counts>0)[0]
        fne = aa[0]*binsz  #first not empty bin
        lne = aa[-1]*binsz #last not empty bin
        
        #left pts of line
        l0 = np.array([fne,0])
        l1 = np.array([rmxb, rmxc]) #alternative given in Ryu or Richardson: replace rmxc with histogram mean value, but it didnt seem to give good result, so we don't use
        slope_left = rmxc/(l1[0]-l0[0]) 
        offs_left = l0[0]*slope_left*(-1)  
        y_left = slope_left*bins+offs_left
        
        #right pts of line
        r0 = np.array([lne,0])
        r1 = np.array([lmxb, lmxc])
        slope_right = lmxc/(r1[0]-r0[0])
        offs_right = r0[0]*slope_right*(-1)
        y_right = slope_right*bins+offs_right
        
        btw_bins = bins[lmax_idx+a+1:rmax_idx+c-1] #between first and second peak
        btw_counts = counts[lmax_idx+a+1:rmax_idx+c-1] #we dont use the 256 counts bin edge here

        if (lmax_idx != rmax_idx) and ( (lmax_idx+a+1) - (rmax_idx+c-1) < 0):

            lb = np.vstack((btw_bins, btw_counts)).T #make the points
            ld = np.cross(l1-l0,l0-lb)/LA.norm(l1-l0) #get the distances
            lmx = np.max(ld) #find max distance
            
            lix = np.where(ld==lmx)[0][0] #find index of max distance
            #apparently, can have multiple with same distance so need be careful. for simplicity just take first one.

            lixa = lix+lmax_idx+a+1 #add back the offset to change from the relative to absolute bin number
            luc = bins[lixa]
            lucl.append(luc)  

            rb = np.vstack((btw_bins, btw_counts)).T
            rd = np.cross(r0-r1,r0-rb)/LA.norm(r1-r0)
            rmx = np.max(rd)
            rix = np.where(rd==rmx)[0][0]
            rixa = rix+lmax_idx+a+1   
            
            ruc = bins[rixa]
            rucl.append(ruc)

        #Calculate gap fraction

            #check if cloudy
            TMC = bins[rixa]+int((bins[lixa] - bins[rixa])*skythr)
            arrbin=arr[:,:,2].copy()
            cldm = (arrbin >= TMC) 
            skyidx = arr[cldm,2].sum()/(arr[cldm,0].sum()+arr[cldm,1].sum())
            skyidxl.append(skyidx)
            print('Sky is cloudy if blue idx %s is less than %s' %(skyidx,cloudythr)) #ryu suggest 0.65, but seems 0.5 ish is more capable here
            
            #set TM according to cloudy. As in other studies, our retrievals (ability to idntify gap with contours) was usually better when cloudy. Clear sky can be dark ...
            if skyidx < cloudythr: #below cloudythr is cloudy.
                tmthr = tmthrc #0.25 is better than Ryu's 0.5 here, for overcast
                #clouds are bright, and as result blue sky is more likely to detected as canopy alongside stem/leaves. To reduce this, decrease thr. 
                #tradeoff: not dense canopy will be identified as sky rather than plant; but at least sky won't be identified as plant. Consistent underdetection works better because that way we're more likely to find contours for 'large gaps' consistently.
            TM = bins[rixa]+int((bins[lixa] - bins[rixa])*tmthr) #0.25 seems to work quite well, but is a problem for NL determination....but 0.5 can also be problematic even blue sky is classified as overcast. This is all very roundabout, values other than 0.25,0.50, 0.75 might work even better. 
            #TM is the single bin identified for the binary plant/sky classification of image
            msk = (arrbin >= TM)
            arrbin[msk] = 1#0 #sky ... putting sky as 1 is important for improved countour finding for determining NL
            arrbin[~msk]= 0#1 #tree 

            nclr = (arrbin == 1).sum()
            ncan = (arrbin == 0).sum()
            GF = nclr/(nclr+ncan)
            gfl.append(GF)
            print('Gap Fraction is %s' %GF)
            
            #now find the total number of pixels located in the large gaps, NL. We as a first (and for now, only) option we accomplish this using cv2.findContours. 
            #In principle it does the correct thing, although there may be better options such as whatever coveR label_gaps() does https://doi.org/10.1007/s00468-022-02338-5; https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.multiscale_graphcorr.html
            cimg = arrbin.copy()
            minc_img = cimg.copy()
            contours, hier = cv2.findContours(cimg,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE) #cv2.CHAIN_APPROX_NONE

            contours2 = []
            for cnt in contours: #eyballing, 1.3% is 48k pixel, roughly contour area 10000 ... eg the smallest vis area is about 300*150 =45k, close ... this turns out to be a bad estimate. the 10k value used in our processing is more like >0.3% than 1.3%
                if cv2.contourArea(cnt) > fcval: 
                    contours2.append(cnt)
                    cv2.drawContours(cimg,[cnt],0,(255,255,255),thickness=cv2.FILLED)
            
            lgc_cnt = (cimg==255).sum()
            clr_cnt = (cimg==1).sum()
            cnp_cnt = (cimg==0).sum()

            NT = cimg.shape[0]*cimg.shape[1]
            lgc_pct = lgc_cnt/NT
            clr_pct = clr_cnt/NT
            cnp_pct = cnp_cnt/NT
            CC = 1-(lgc_cnt/NT)
            
            sorted_contours = sorted(contours2, key=cv2.contourArea)
            if len(sorted_contours) > 0:
                tmp_cnt = sorted_contours[0]
                cv2.drawContours(minc_img,[tmp_cnt],0,(255,255,255),thickness=cv2.FILLED)
                minpix_cnt = (minc_img==255).sum()
                minpixarea = minpix_cnt/NT*100
                print('minpix count is {0}'.format(minpix_cnt))
                minpixareal.append(minpixarea)
            elif len(sorted_contours) == 0:
                minpixareal.append(-1)
            
            ccl.append(CC)
            print('large gap pixel (NL), clear, canopy pixel counts are %s, %s, %s or %s, %s, %s of image' %(lgc_cnt,clr_cnt,cnp_cnt,lgc_pct,clr_pct,cnp_pct))
            print('Faction of crown cover CC is %s' %CC)
            
            CP = 1 - (1-GF)/CC
            cpl.append(CP)
            print('Crown porosity CP is %s' %CP)
            
            PAI = -CC*np.log(CP)/k
            pail.append(PAI)
            print('Plant Area Index PAI is %s \n' %PAI)
            
        #make some plots
            fig, ax = plt.subplots(2,2, figsize=(9, 6))
            ax[0][0].title.set_text('Rosin (2001), up: {0}, lw: {1}, $\\Delta$: {2}'.format(luc,ruc,luc-ruc))
            ax[0][0].bar(bins[:-1],counts,width=2)
            ax[0][0].axvline(x=TM,color='k',linestyle=':')
            ax[0][0].annotate('tree-sky thr bin is {0}'.format(str(TM)),(TM,1.1*counts_max), size=8)
            
            #left
            ax[0][0].scatter(x=bins, y=y_left)
            ax[0][0].scatter(x=l0[0],y=l0[1],color='r',marker='o',s=100)
            ax[0][0].scatter(x=l1[0],y=rmxc,color='r',marker='o',s=100)
            
            #right    
            ax[0][0].scatter(x=bins, y=y_right)
            ax[0][0].scatter(x=r0[0],y=r0[1],color='k',marker='o',s=100)
            ax[0][0].scatter(x=r1[0],y=lmxc,color='k',marker='o',s=100)

            #mark ROSIN bins
            ax[0][0].scatter(x=bins[lixa], y=counts[lixa],color='r',marker='x',s=100) 
            ax[0][0].scatter(x=bins[rixa], y=counts[rixa],color='k',marker='x',s=100)
            
            #show binary canopy (0)/sky (yellow)
            ax[0][1].title.set_text('Canopy (=0) and (=1) Sky {0}'.format(np.round(skyidx,3)))
            ax[0][1].imshow(arrbin,vmin=0,vmax=1)
            
            #show large gap for calculate NL (yellow)
            ax[1][0].title.set_text('Large gaps in canopy (=255)')
            ax[1][0].imshow(cimg, cmap='viridis', vmin=0,vmax=2)
            
            #input image
            ax[1][1].title.set_text('Orig')
            ax[1][1].imshow(arr)#, cmap='viridis', vmin=0,vmax=2)

            plt.suptitle(indir+' at '+datetime.strftime(bb, format ='%m-%d-%Y %H:%M:%S') + '. Cloud: '+str(skyidx<cloudythr) +' PAI: '+str(np.round(PAI,3)), fontweight='bold')
            plt.savefig('hist_'+indir+'_'+val, dpi=dpi) 
            plt.close('all')
            
        else:
            lucl.append(-1)
            rucl.append(-1)
            skyidxl.append(-1)
            gfl.append(-1)
            ccl.append(-1)
            cpl.append(-1)
            pail.append(-1)
            minpixareal.append(-1)

            fig, ax = plt.subplots(2,2, figsize=(9, 6))
            ax[0][0].title.set_text('Rosin (2001), up: {0}, lw: {1}, $\\Delta$: {2}'.format('NA','NA','NA'))
            ax[0][0].bar(bins[:-1],counts,width=2)
            
            #left
            ax[0][0].scatter(x=bins, y=y_left)
            ax[0][0].scatter(x=l0[0],y=l0[1],color='r',marker='o',s=100)
            ax[0][0].scatter(x=l1[0],y=rmxc,color='r',marker='o',s=100)
            
            #right    
            ax[0][0].scatter(x=bins, y=y_right)
            ax[0][0].scatter(x=r0[0],y=r0[1],color='k',marker='o',s=100)
            ax[0][0].scatter(x=r1[0],y=lmxc,color='k',marker='o',s=100)
            
            #input image
            ax[1][1].title.set_text('Orig')
            ax[1][1].imshow(arr)#, cmap='viridis', vmin=0,vmax=2)

            plt.suptitle(indir+' at '+datetime.strftime(bb, format ='%m-%d-%Y %H:%M:%S') + '. Cloud: '+'NA' +' PAI: '+'NA', fontweight='bold')
            plt.savefig('hist_'+indir+'_'+val, dpi=dpi) 
            plt.close('all')
            
            print('***could not classify, skipping calculations (check plot)*** \n')
        
    #put important outputs to list and export as csv
    d = {'name': fn, 'lmxb': leftmaxbin, 'lmxc': leftmaxcount, 'rmxb': rightmaxbin, 'rmxc': rightmaxcount, 'rb_l': lucl, 'rb_r': rucl, 'sky': skyidxl, 'minpixarea': minpixareal, 'GF': gfl, 'CC': ccl, 'CP': cpl, 'PAI': pail}
    yy = pd.DataFrame(data = d, index = dt)
    return yy

if __name__ == '__main__':

    inps = cmdLineParse() # parse command line inputs
    nme = inps.indir#.split('_')[0]
    csvout = '2_process_{0}.csv'.format(nme)
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd,inps.indir,csvout)) == False:
        yy = get_PAI(inps.indir)
        yy.to_csv(os.path.join(cwd,inps.indir,csvout))
    else:
        print('No new data, skipping calculation')
        


