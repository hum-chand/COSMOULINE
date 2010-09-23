#
#	We measure level and stddev of the sky, with custom python.
#	You can turn on the flag "checkplots" to check how I do this.
#

execfile("../config.py")
from kirbybase import KirbyBase, KBError

from variousfct import *
from datetime import datetime, timedelta
import pyfits
import numpy as np

if checkplots :
	import matplotlib.pyplot as plt

# We select the images :
db = KirbyBase()
if thisisatest :
	print "This is a test run."
	images = db.select(imgdb, ['gogogo','treatme', 'testlist'], [True, True, True], returnType='dict')
else :
	images = db.select(imgdb, ['gogogo','treatme'], [True, True], returnType='dict')

nbrofimages = len(images)
print "Number of images to treat :", nbrofimages
proquest(askquestions)

if not checkplots : # Then we will update the database.
	# We make a backup copy of our database :
	backupfile(imgdb, dbbudir, "skystats")

	# We add some new fields into the holy database :
	if "skylevel" not in db.getFieldNames(imgdb) :
		db.addFields(imgdb, ['skylevel:float', 'prealistddev:float'])


starttime = datetime.now()

for i,image in enumerate(images):

	print "- " * 40
	print "%i / %i : %s" % (i+1, nbrofimages, image['imgname'])
	
	# Read the FITS file as numpy array :
	pixelarray, header = pyfits.getdata(image['rawimg'], header=True)
	pixelarray = np.asarray(pixelarray).transpose() # This is to put it in right orientation, would not be needed here.
	
	# Print some info about the image :
	pixelarrayshape = pixelarray.shape
	print "(%i, %i), %s, %s" % (pixelarrayshape[0], pixelarrayshape[1], header["BITPIX"], pixelarray.dtype.name)
	
	# Ready to rock.
	# So we want to get the sky level, and the std dev of the pixels around this level (noise in sky).
	medianlevel = np.median(pixelarray.ravel())
	
	# We cut between 0 and twice the medianlevel :
	nearskypixvals = pixelarray[np.logical_and(pixelarray > 0, pixelarray < 2*medianlevel)]
	
	# This would be needed to fit gaussians etc :
	#(hist, bin_edges) = np.histogram(nearskypixvals, bins=np.linspace(0,2*medianlevel,200), range=None, normed=True, weights=None, new=True)
	#bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
	# But we will keep it simple :
	
	# First approximation :
	skylevel = np.median(nearskypixvals.ravel())
	skystddev = np.std(nearskypixvals.ravel())
	
	# we iterate once more, cutting at 4 sigma :
	nearskypixvals = nearskypixvals[np.logical_and(nearskypixvals > skylevel - 4.0 * skystddev, nearskypixvals < skylevel + 4.0 * skystddev)]
	
	# Final approximation :
	skylevel = np.median(nearskypixvals.ravel())
	skystddev = np.std(nearskypixvals.ravel())
	
	print "Sky level at %f, noise of %f" % (skylevel, skystddev)
		
	if checkplots :
		plt.hist(pixelarray.ravel(), facecolor='green', bins=np.linspace(0,3*medianlevel,100), normed=True, log=False)
		#plt.plot(bin_centers, hist, "b.")
		plt.axvline(x=medianlevel, linewidth=2, color='green')
		plt.axvline(x=skylevel, linewidth=2, color='red')
		plt.axvline(x=skylevel - 1*skystddev, linewidth=2, color='blue')
		plt.axvline(x=skylevel + 1*skystddev, linewidth=2, color='blue')
		plt.xlabel("Pixel value [ADU]")
		plt.show()
		print "Remember : the database is NOT UPDATED !"
	else:
		db.update(imgdb, ['recno'], [image['recno']], {'skylevel': float(skylevel), 'prealistddev': float(skystddev)})
	
if not checkplots :
	db.pack(imgdb) # To erase the blank lines
	

endtime = datetime.now()
timetaken = nicetimediff(endtime - starttime)

notify(computer, withsound, "I'me done. It took me %s" % timetaken)
