import sys, numpy, datetime, glob, scipy
from scipy import misc
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from multiprocessing import Pool
from pylab import figure, axes, pie, title, show
#Script takes in a timepoint, speciment, cameras list (ie. 0,1 or 0 or 1) and channel list 

path = sys.argv[1]
timepoint = sys.argv[2]
specimen = sys.argv[3]
cameras = sys.argv[4].split(',')
channels = sys.argv[5].split(',')
specimenString = specimen.zfill(2)
timepointString = timepoint.zfill(5)
path = path+'/SPM' + specimenString + '/TM' + timepointString + '/ANG000/'

def insertImage(camera, channel, plane):
    imagePath = path + 'SPC' + specimenString + '_TM' + timepointString + '_ANG000_CM' + camera + '_CHN' + channel.zfill(2) + '_PH0_PLN' + str(plane).zfill(4) + '.tif'
    return misc.imread(imagePath)


if __name__ == '__main__':
    pool = Pool(processes=32)
    numberOfChannels = len(channels) 
    numberOfCameras = len(cameras)
    #fig, ax = plt.subplots(nrows = numberOfChannels, ncols = 2*numberOfCameras)#, figsize=(16,8))
    fig = plt.figure();
    fig.set_size_inches(16,8)
    outer = gridspec.GridSpec(numberOfChannels, numberOfCameras, wspace = 0.3, hspace = 0.3)
    
    for channelCounter, channel in enumerate(channels):
        for cameraCounter, camera in enumerate(cameras):
            inner = gridspec.GridSpecFromSubplotSpec(1,2, subplot_spec = outer[cameraCounter, channelCounter], wspace=0.1, hspace=0.1)
            newList = [(camera, channel, 0)]
            numberOfPlanes = len(glob.glob1(path, '*CM'+camera+'_CHN'+channel.zfill(2)+'*'))
            for plane in range(1,numberOfPlanes):
                newList.append((camera, channel, plane))
                
            images = pool.starmap(insertImage,newList)
            images = numpy.asarray(images).transpose(1,2,0)
            xy = numpy.amax(images,axis=2)
            xz = numpy.amax(images,axis=1)
            ax1 = plt.Subplot(fig, inner[0])
            ax1.imshow(xy, cmap='gray')
            fig.add_subplot(ax1)
            ax1.axis('auto')
            ax2 = plt.Subplot(fig, inner[1])
            ax2.imshow(xz, cmap='gray')
            fig.add_subplot(ax2)
            ax2.axis('auto')
            ax2.get_yaxis().set_visible(False)
            #ax1.get_shared_y_axes().join(ax1, ax2)
            baseString = 'CM' + camera + '_CHN' + channel.zfill(2)
            ax1.set_title(baseString + ' xy')#, fontsize=12)
            ax2.set_title(baseString + ' xz')#, fontsize=12)
    
    fig.savefig('/groups/lightsheet/lightsheet/home/ackermand/flask/lightsheetInterface/app/static/test.jpg')
    pool.close()

