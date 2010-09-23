#
#	In this module we define the functions that know how to read the headers of the various telescopes,
#	and calculate things like dates and exptimes from these headers.
#
#	They return a dict that HAS to match the minimaldbfields defined in addtodatabase.

#	Definition for mjd used in cosmouline is the good and only one : mjd = jd - 2400000.5

# scalefactor of the set is something proportional to a "long range" inverse pixel size : for instance the distance in pixels between two stars stars.
# It will be used for star identification only : no direct impact on the *quality* of the alignment, but could decide on how many stars
# will be used for this alignment ...

# telescopeelevation is in meters, position in deg:min:sec

# gain is in electrons / ADU

# readnoise is in electrons ("per pixel"). At least this is how cosmic.py will use it...

import sys
import datetime
import pyfits
import math

from variousfct import *

execfile("../config.py") # yes, this line is required so that settings.py are available within the functions below.


def juliandate(pythondt):
	"""
	Returns the julian date from a python datetime object
	"""
	
	#year = int(year)
	#month = int(month)
	#day = int(day)
	
	year = int(pythondt.strftime("%Y"))
	month = int(pythondt.strftime("%m"))
	day = int(pythondt.strftime("%d"))
	
	hours = int(pythondt.strftime("%H"))
	minutes = int(pythondt.strftime("%M"))
	seconds = int(pythondt.strftime("%S"))
	
	fracday = float(hours + float(minutes)/60.0 + float(seconds)/3600.0)/24.0
	#fracday = 0
	
	# First method, from the python date module. It was wrong, I had to subtract 0.5 ...
	a = (14 - month)//12
        y = year + 4800 - a
        m = month + 12*a - 3
        jd1 = day + ((153*m + 2)//5) + 365*y + y//4 - y//100 + y//400 - 32045
	jd1 = jd1 + fracday - 0.5
	
	# Second method (I think I got this one from Fundamentals of Astronomy)
	# Here the funny -0.5 was part of the game.
	
	j1 = 367*year - int(7*(year+int((month+9)/12))/4)
	j2 = -int((3*((year + int((month-9)/7))/100+1))/4)
	j3 = int(275*month/9) + day + 1721029 - 0.5
	jd2 = j1 + j2 + j3 + fracday
	
	#print "Date: %s" % pythondt.strftime("%Y %m %d  %H:%M:%S")
	#print "jd1 : %f" % jd1
	#print "jd2 : %f" % jd2
	
	# This never happened...
	if abs(jd1 - jd2) > 0.00001:
		print "ERROR : julian dates algorithms do not agree..."
		sys.exit(1)
	
	return jd2
	

def DateFromJulianDay(JD):
	"""

	Currently this is not used by cosmouline, but it fits here quite nicely...

	Returns the Gregorian calendar
	Based on wikipedia:de and the interweb :-)
	"""

	if JD < 0:
		raise ValueError, 'Julian Day must be positive'

	dayofwk = int(math.fmod(int(JD + 1.5),7))
	(F, Z) = math.modf(JD + 0.5)
	Z = int(Z)
    
	if JD < 2299160.5:
		A = Z
	else:
		alpha = int((Z - 1867216.25)/36524.25)
		A = Z + 1 + alpha - int(alpha/4)


	B = A + 1524
	C = int((B - 122.1)/365.25)
	D = int(365.25 * C)
	E = int((B - D)/30.6001)

	day = B - D - int(30.6001 * E) + F
	nday = B-D-123
	if nday <= 305:
		dayofyr = nday+60
	else:
		dayofyr = nday-305
	if E < 14:
		month = E - 1
	else:
		month = E - 13

	if month > 2:
		year = C - 4716
	else:
		year = C - 4715

	
	# a leap year?
	leap = 0
	if year % 4 == 0:
		leap = 1
  
	if year % 100 == 0 and year % 400 != 0: 
		print year % 100, year % 400
		leap = 0
	if leap and month > 2:
		dayofyr = dayofyr + leap
	
    
	# Convert fractions of a day to time    
	(dfrac, days) = math.modf(day/1.0)
	(hfrac, hours) = math.modf(dfrac * 24.0)
	(mfrac, minutes) = math.modf(hfrac * 60.0)
	seconds = round(mfrac * 60.0) # seconds are rounded
    
	if seconds > 59:
		seconds = 0
		minutes = minutes + 1
	if minutes > 59:
		minutes = 0
		hours = hours + 1
	if hours > 23:
		hours = 0
		days = days + 1

	return datetime.datetime(year,month,int(days),int(hours),int(minutes),int(seconds))
    



###############################################################################################

# And now the functions that know how to read the headers

###############################################################################################

def eulerheader(rawimg):
	print rawimg
	imgname = setname + "_" + os.path.splitext(os.path.basename(rawimg))[0] # drop extension
	
	pixsize = 0.344
	readnoise = 9.5 # Taken from Christel
	scalingfactor = 0.5612966 # measured scalingfactor (with respect to Mercator = 1.0)
	
	telescopelongitude = "-70:43:48.00"
	telescopelatitude = "-29:15:24.00"
	telescopeelevation = 2347.0
		
	header = pyfits.getheader(rawimg)
	availablekeywords = header.ascardlist().keys()
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"
	
	if "DATE-OBS" in availablekeywords: # This should be the default way of doing it.
		pythondt = datetime.datetime.strptime(header["DATE-OBS"][0:19], "%Y-%m-%dT%H:%M:%S") # This is the start of the exposure.
	else:
		if "TUNIX_DP" in availablekeywords: # For the very first images
			pythondt = datetime.datetime.utcfromtimestamp(float(header["TUNIX_DP"]))
			print "I have to use TUNIX_DP :", pythondt
			
	if "EXPTIME" in availablekeywords: # Nearly always available.
		exptime = float(header['EXPTIME']) # in seconds.
	elif "TIMEFF" in availablekeywords:
			exptime = float(header['TIMEFF'])
			print "I have to use TIMEFF :", exptime
	else:
		print "WTF ! No exptime !"
		exptime = 360.0
		
	pythondt = pythondt + datetime.timedelta(seconds = exptime/2.0) # This is the middle of the exposure.
	
	# Now we produce the date and datet fields, middle of exposure :
	
	date = pythondt.strftime("%Y-%m-%d")
	datet = pythondt.strftime("%Y-%m-%dT%H:%M:%S")

	myownjdfloat = juliandate(pythondt) # The function from headerstuff.py
	myownmjdfloat = myownjdfloat - 2400000.5
	
	# We perform some checks with other JD-like header keywords if available :
	if "MJD-OBS" in availablekeywords:
		headermjdfloat = float(header['MJD-OBS']) # should be the middle of exposure, according to hdr comment.
		if abs(headermjdfloat - myownmjdfloat) > 0.0001:
			raise mterror("MJD-OBS disagrees !")
	
	jd = "%.6f" % myownjdfloat 
	mjd = myownmjdfloat
		
	rotator = 0.0
	
	# The gain, we need to read 3 headers.
	# The options are written in order of "trust", the most trusted first.
	gain = 0.0
	if "CCD_SGAI" in availablekeywords: # old images
		gain = float(header['CCD_SGAI'])
		print "Reading gain from CCD_SGAI"
	elif "OGE DET SGAI" in availablekeywords: # intermediary, just after the header format change
		gain = float(header['HIERARCH OGE DET SGAI'])
		print "Reading gain from OGE DET SGAI"
	elif "ESO CAM CCD SGAI" in availablekeywords: # The current format
		gain = float(header['HIERARCH ESO CAM CCD SGAI'])
		print "Reading gain from ESO CAM CCD SGAI"
	elif "ESO CAM2 CCD GAIN" in availablekeywords: # was also used once in the transition phase 04/2009
		gain = float(header["HIERARCH ESO CAM2 CCD GAIN"])
		print "Reading gain from ESO CAM2 CCD GAIN"
	elif "ESO CAM CCD GAIN" in availablekeywords: # was also used once in the transition phase 04/2009
		gain = float(header["HIERARCH ESO CAM CCD GAIN"])
		print "Reading gain from ESO CAM CCD GAIN"
	elif "CCD_FGAI" in availablekeywords: # Very very old ones ... Be careful, this was in ADU/e
		gain = 1.0 / float(header["CCD_FGAI"])
	
	# We do a quick check :
	if gain < 0.5 or gain > 3.0:
		print availablekeywords
		raise mterror("gain = %f ???" % gain)
	
	# The pre-reduction info :
	#preredcomment1 = "None"
	#preredcomment2 = "None"
	#preredfloat1 = 0.0
	#preredfloat2 = 0.0
	preredcomment1 = str(header["PR_NFLAT"])
	preredcomment2 = str(header["PR_NIGHT"])
	preredfloat1 = float(header["PR_FSPAN"])
	preredfloat2 = float(header["PR_FDISP"])
	
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,'testcomment':testcomment ,
	'telescopename':telescopename, 'setname':setname, 'rawimg':rawimg, 
	'scalingfactor':scalingfactor, 'pixsize':pixsize, 'date':date, 'datet':datet, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain, 'readnoise':readnoise, 'rotator':rotator,
	'preredcomment1':preredcomment1, 'preredcomment2':preredcomment2, 'preredfloat1':preredfloat1, 'preredfloat2':preredfloat2
	}
	
	return returndict


###############################################################################################


def mercatorheader(rawimg):
	
	print rawimg
	imgname = setname + "_" + os.path.splitext(os.path.basename(rawimg))[0] # drop extension
	
	pixsize = 0.19340976
	gain = 0.93 # e- / ADU, as given by Saskia Prins
	readnoise = 9.5 # ?
	scalingfactor = 1.0 # By definition, others are relative to Mercator.
	
	telescopelongitude = "-17:52:47.99"
	telescopelatitude = "28:45:29.99"
	telescopeelevation = 2327.0
	
	header = pyfits.getheader(rawimg)
	availablekeywords = header.ascardlist().keys()
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"


	if len(header["DATE-OBS"]) >= 19:
		pythondt = datetime.datetime.strptime(header["DATE-OBS"][0:19], "%Y-%m-%dT%H:%M:%S")
	
	if len(header["DATE-OBS"]) == 10:
		pythondt = datetime.datetime.utcfromtimestamp(float(header["TUNIX_DP"]))			
		print "Warning : I had to use TUNIX_DP : %s" % pythondt
		print "(But this should be ok)"
	
	exptime = float(header['EXPTIME']) # in seconds.
	
	pythondt = pythondt + datetime.timedelta(seconds = exptime/2.0) # This is the middle of the exposure.
	
	# Now we produce the date and datet fields, middle of exposure :
	
	date = pythondt.strftime("%Y-%m-%d")
	datet = pythondt.strftime("%Y-%m-%dT%H:%M:%S")

	myownjdfloat = juliandate(pythondt) # The function from headerstuff.py
	myownmjdfloat = myownjdfloat - 2400000.5
	
	# We perform some checks with other JD-like header keywords if available :
	if "MJD" in availablekeywords:
		headermjdfloat = float(header['MJD']) # should be the middle of exposure, according to hdr comment.
		if abs(headermjdfloat - myownmjdfloat) > 0.0001:
			raise mterror("MJD disagrees !")
	
	jd = "%.6f" % myownjdfloat 
	mjd = myownmjdfloat
	
	
	# Other default values
	rotator = 0.0
	
	# The pre-reduction info :
	preredcomment1 = header["PR_FTYPE"]
	preredcomment2 = header["PR_NIGHT"]
	preredfloat1 = float(header["PR_BIASL"])
	preredfloat2 = float(header["PR_OVERS"])
	
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,'testcomment':testcomment ,
	'telescopename':telescopename, 'setname':setname, 'rawimg':rawimg, 
	'scalingfactor':scalingfactor, 'pixsize':pixsize, 'date':date, 'datet':datet, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain, 'readnoise':readnoise, 'rotator':rotator,
	'preredcomment1':preredcomment1, 'preredcomment2':preredcomment2, 'preredfloat1':preredfloat1, 'preredfloat2':preredfloat2
	}

	return returndict



###############################################################################################

def noheader(rawimg):
	
	print rawimg
	imgname = setname + "_" + os.path.splitext(os.path.basename(rawimg))[0] # drop extension
	
	pixsize = 1.0
	gain = 1.0
	readnoise = 5.0
	scalingfactor = 1.0
	
	telescopelongitude = "00:00:00.00"
	telescopelatitude = "00:00:00.00"
	telescopeelevation = 0.0
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"
	
	pythondt = datetime.datetime.strptime("2000-00-00T00:00:00", "%Y-%m-%dT%H:%M:%S")
	exptime = 300.0
	pythondt = pythondt + datetime.timedelta(seconds = exptime/2.0) # This is the middle of the exposure.
	
	# Now we produce the date and datet fields, middle of exposure :
	date = pythondt.strftime("%Y-%m-%d")
	datet = pythondt.strftime("%Y-%m-%dT%H:%M:%S")

	myownjdfloat = juliandate(pythondt)
	myownmjdfloat = myownjdfloat - 2400000.5
	jd = "%.6f" % myownjdfloat 
	mjd = myownmjdfloat
	
	# Other default values
	rotator = 0.0
	
	# The pre-reduction info :
	preredcomment1 = "None"
	preredcomment2 = "None"
	preredfloat1 = 0.0
	preredfloat2 = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,'testcomment':testcomment ,
	'telescopename':telescopename, 'setname':setname, 'rawimg':rawimg, 
	'scalingfactor':scalingfactor, 'pixsize':pixsize, 'date':date, 'datet':datet, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain, 'readnoise':readnoise, 'rotator':rotator,
	'preredcomment1':preredcomment1, 'preredcomment2':preredcomment2, 'preredfloat1':preredfloat1, 'preredfloat2':preredfloat2
	}

	return returndict



###############################################################################################


"""
if telescopename == "Liverpool":
	#pixsize = 0.279 # (if a 2 x 2 binning is used)
	pixsize = 0.135 # (if a 1 x 1 binning is used, as we do for cosmograil)
	gain = 0 # We will take it from the header, it's around 2.2, keyword GAIN
	readnoise = 0.0 # idem, keyword READNOIS, 7.0
	scalingfactor = 1.0 # Not measured : to be done !

	telescopelongitude = "-17:52:47.99" # Same location then Mercator ...
	telescopelatitude = "28:45:29.99"
	telescopeelevation = 2327.0
	
	# To put images into natural orientation : invert X and rotate 270
	

if telescopename == "MaidanakSITE":	# MaidanakSITE = Maidanak nitrogen cooled camera
	pixsize = 0.266
	gain = 1.16
	readnoise = 5.3
	scalingfactor = 0.723333 # measured scalingfactor (with respect to Mercator = 1.0)
	
	telescopelongitude = "66:53:47.07"
	telescopelatitude = "38:40:23.95"
	telescopeelevation = 2593.0


if telescopename == "MaidanakSI":	# MaidanakSI = korean 4k x 4k CCD
	pixsize = 0.266			# yes, it's the same pixel size as SITE
	gain = 1.45
	readnoise = 4.7
	scalingfactor = 0.721853 # measured scalingfactor (with respect to Mercator = 1.0)
	
	telescopelongitude = "66:53:47.07"
	telescopelatitude = "38:40:23.95"
	telescopeelevation = 2593.0


if telescopename == "MaidanakPeltier":	# Maidanak Peltier cooled CCD (something like a SBIG)
	pixsize = 0.43025		# quick and dirty, from measured scalingfactor
	gain = 1.4
	readnoise = 5.0
	scalingfactor = 0.449525 # measured scalingfactor (with respect to Mercator = 1.0)
	
	telescopelongitude = "66:53:47.07"
	telescopelatitude = "38:40:23.95"
	telescopeelevation = 2593.0

"""

"""
if telescopename == "HCT":
	pixsize = 0.296
	gain = 1.22
	readnoise = 4.7
	scalingfactor = 0.65189
	
	telescopelongitude = "78:57:50.99"
	telescopelatitude = "32:46:46.00"
	telescopeelevation = 4500.0


if telescopename == "NOTalfosc":
	pixsize = 0.188 # was written somewhere in one header
	gain = 1.5 # this is unknown, I have no idea
	readnoise = 5.0	# same remark
	scalingfactor = 1.01516 # measured, with respect to mercator = 1.0

	
	telescopelongitude = "-17:52:47.99"
	telescopelatitude = "28:45:29.99"
	telescopeelevation = 2327.0


if telescopename == "HoLi":
	pixsize = 0.21 # Holicam, taken from http://www.astro.uni-bonn.de/~ccd/holicam/holicam.htm
	gain = 2.5 # idem 
	readnoise = 9.0 # idem
	scalingfactor = 1.0 # not yet measured ! Do so  !

	telescopelongitude = "6:51:00.00"
	telescopelatitude = "50:09:48.00"
	telescopeelevation = 549.0
	# Images are in natural orientation



if telescopename == "NOHEADER":
	pixsize = 0.126
	gain = 1.0
	readnoise = 10.0
	scalingfactor = 1.0

	telescopelongitude = "00:00:00.00"
	telescopelatitude = "00:00:00.00"
	telescopeelevation = 0.0
	


def liverpoolheader(rawimg):
	print rawimg
	imgname = setname + "_" + os.path.splitext(os.path.basename(rawimg))[0] # drop extension
	
	header = pyfits.getheader(rawimg)
	
	# telescopename, setname, scalingfactor, pixsize
	# are known (global)
	gain = float(header['GAIN'])
	readnoise = float(header['READNOIS'])
	
	binning = int(header['CCDXBIN'])
	if binning != 2:
		raise mterror("Binning is not 2 x 2 !")
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	exptime = float(header['EXPTIME'])
	date = str(header['DATE']) # This is in UTC, format like 2008-04-11
	# JD does not exist, so we calculate it from the 
	
	dateobs = str(header['DATE-OBS']) # beginning of exp in UTC
	d = dateobs[0:10] # should be the same then DATE
	if d != date:
		raise mterror("DATE-OBS and DATE disagree ! %s %s" % (d, date))
	h = int(dateobs[11:13])
	m = int(dateobs[14:16])
	s = int(dateobs[17:19])
	
	utcent = exptime/2 + s + 60*m + 3600*h
	jd = str(chandrajuliandate(d, utcent))
	
	mjd = float(header['MJD'])
	if abs(float(jd) - 2400000.5 - mjd) > 0.01: # loose, as we have added exptime/2 ...
		print "mjd -> %f" % (mjd + 2400000.5)
		print "jd  -> %s" % jd
		raise mterror("WARNING : header JD and MJD disagree !!!")
	
	rotator = float(header['ROTSKYPA'])
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict


def hctheader(rawimg): # and for the chandra telescope
	print rawimg
	
	imgname = setname + "_" + rawimg.split("/")[-1].split(".")[0] # drop extension
	
	header = pyfits.getheader(rawimg)
	
	# telescopename, setname, scalingfactor, pixsize
	# are known (global)
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	date = header['DATE-OBS'] # format like 2008-04-11
	#print date
	exptime = float(header['EXPTIME'])
	#print exptime
	
	gaintext = str(header['GAINM'])
	if gaintext != "HIGH":
		raise mterror("Unknown GAINM")
	
	utstart = int(header['TM_START'])
	utend = int(header['TM_END'])
	#print utstart
	#print utend
	if (utend - utstart) > 600:
		raise mterror("Oh boy, error 58877HGY8")
	utcent = (utstart + exptime/2.0)
	
	jd = chandrajuliandate(date, utcent)
	mjd = jd - 2400000.5 
	jd = "%.10f" % jd # convert to string
	
	rotator = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict


def koreanheader(rawimg): # this reads the korean 4k by 4k camera files from Maidanak
	print rawimg
	
	imgname = setname + "_" + rawimg.split("/")[-1].split(".")[0] # drop extension
	header = pyfits.getheader(rawimg)
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	date = header['UTDATE'] # format like 2008-04-11
	#print date
	exptime = float(header['EXPTIME']) # this is in seconds
	#print exptime
	utstart = header['UTSTART'] 	# this is a sting like '18:37:51'
	# convert this to the utcent of Chandra, and then use the same fct to calc JD.
	uthour = int(utstart.split(':')[0])
	utmin = int(utstart.split(':')[1])
	utsec = int(utstart.split(':')[2])

	utcent = uthour*3600. + utmin*60. + utsec + exptime/2.0

	jd = chandrajuliandate(date, utcent)
	mjd = jd - 2400000.5 
	jd = "%.10f" % jd # convert to string
	# mjd = "%.10f" % mjd # NO, as we keep mjd as a float now.
	
	rotator = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict

def peltierheader(rawimg): # this reads the peltier-cooled camera files from Maidanak
	print rawimg
	
	imgname = setname + "_" + rawimg.split("/")[-1].split(".")[0] # drop extension
	header = pyfits.getheader(rawimg)
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	longdate = header['DATE-OBS'] # format like 2008-02-24T20:14:15.422 in UTC
	date = longdate.split('T')[0]
	#print date
	
	exptime = float(header['EXPTIME']) # this is in seconds
	
	utstart = longdate.split('T')[1] # this is a sting like '18:37:51.346'

	uthour = float(utstart.split(':')[0])
	utmin = float(utstart.split(':')[1])
	utsec = float(utstart.split(':')[2])
	utcent = uthour*3600. + utmin*60. + utsec + exptime/2.0

	jd = chandrajuliandate(date, utcent)
	mjd = jd - 2400000.5 
	jd = "%.10f" % jd # convert to string
	#mjd = "%.10f" % mjd # NO, as we keep mjd as a float now.
	
	rotator = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict

def notalfoscheader(rawimg): # NOT ALFOSC camera
	print rawimg
	
	imgname = setname + "_" + rawimg.split("/")[-1].split(".")[0] # drop extension
	
	header = pyfits.getheader(rawimg)
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	date = header['DATE-OBS'][:10] # format like 2008-04-11, it's the end of the observation
					# we need this [:10], sometimes there is also the time given...
	print date
	exptime = float(header['EXPTIME'])
	print exptime
	
	#gaintext = str(header['GAINMODE'])		# cannot use this, it's not in every header...
	#if gaintext != "HIGH":
	#		raise mterror("Unknown GAINM")
	
	utstart = int(header['TM_START'])
	utend = int(header['TM_END'])
	print utstart
	print utend
	if abs(utend - utstart) > 600:
		raise mterror("Oh boy, error 58877HGY8")
	utcent = (utstart + exptime/2.0)
	
	jd = chandrajuliandate(date, utcent)
	# we perform a quick test to compare with the original JD :
	
	if "JD" in header:
		headerjd = header["JD"]
		if abs(jd - headerjd) > 0.01:
			raise mterror("JD disagree")
	
	mjd = jd - 2400000.5 
	jd = "%.10f" % jd # convert to string
	
	rotator = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict

def holiheader(rawimg): # HoLiCam header
	print rawimg
	
	imgname = setname + "_" + os.path.splitext(os.path.basename(rawimg))[0] # drop extension
	
	header = pyfits.getheader(rawimg)
	
	# telescopename, setname, scalingfactor, pixsize
	# are known (global)
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	#date = str(header['DATE-OBS']) # this does not work for Holicam, funny problem.
	# But there is an alternative :
	headerascardlist = header.ascardlist()
	headerascardlist["DATE-OBS"].verify("fix")
	date = headerascardlist["DATE-OBS"].value[0:10]
	
	mjd = float(header['MJD'])
	jd = mjd + 2400000.5
	jd = "%.10f" % jd # convert to string

	exptime = float(header['EXPTIME'])
		
	rotator = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict

def noheader(rawimg):	# We do not read the header, only return default values...
	print "No header from", rawimg
	
	imgname = setname + "_" + rawimg.split("/")[-1].split(".")[0] # drop extension
	
	treatme = True
	gogogo = True
	whynot = "na"
	testlist = False
	testcomment = "na"

	longdate = "0000-00-00T00:00:00.0000" # format like 2008-02-24T20:14:15.422 in UTC
	print longdate
	date = longdate.split('T')[0]
	
	exptime = 123.45 # this is in seconds
	
	jd = 2400000.5	# mjd will be 0.0 !
	mjd = jd - 2400000.5 
	jd = "%.10f" % jd # convert to string
	
	rotator = 0.0
	
	# We return a dictionnary containing all this info, that is ready to be inserted into the database.
	
	returndict = {'imgname':imgname, 'treatme':treatme, 'gogogo':gogogo, 'whynot':whynot, 'testlist':testlist,
	'testcomment':testcomment ,'telescopename':telescopename, 'setname':setname,
	'rawimg':rawimg, 'scalingfactor':scalingfactor, 'pixsize':pixsize,
	'date':date, 'jd':jd, 'mjd':mjd,
	'telescopelongitude':telescopelongitude, 'telescopelatitude':telescopelatitude, 'telescopeelevation':telescopeelevation,
	'exptime':exptime, 'gain':gain,
	'readnoise':readnoise, 'rotator':rotator}
	
	return returndict
"""



###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################














###############################################################################################


# Should not be used anymore, refer to the function juliandate.
"""
def chandrajuliandate(date, utcent):
	#Calculates the julian date from 
	#- date : yyyy-mm-dd
	#- utcent : number of seconds since 0:00
	
	import time
	import sys
	#import math
	
	if len(date.split('-')) != 3:
		print "Huge problem  !"
		sys.exit()
		 
	(year, month, day) = date.split('-')
	year = int(year)
	month = int(month)
	day = int(day)
	
	#hours = utcent / 3600.0
	#hour = int(math.floor(hours))
	#inutes = (hours - hour)*60.0
	#minute = int(math.floor(minutes))
	#seconds = (minutes-minute)*60.0
	#second = int(math.floor(seconds))
	
	#if abs((second+60*minute+3600*hour)-utcent) > 2:
	#	print "Nasty error"
	#	sys.exit()
	
	#t = time.mktime((year, month, day, hour, minute, second, 0, 0, 0))
	#print t
	
	fracday=utcent/86400.0

	j1 = 367*year - int(7*(year+int((month+9)/12))/4)
	j2 = -int((3*((year + int((month-9)/7))/100+1))/4)
	j3 = int(275*month/9) + day + 1721029 - 0.5
	jd = j1 + j2 + j3 + fracday
	
	#print jd
	
	return jd
"""



"""
Old stuff from Christel :

############
# Maidanak #
############

full size = 2030x800 pixels
scale = 0.266" per pixel
field of view = 8.5x3.5 arcmin
readout noise = 5.3 e- 
gain = 1.16 e-/ADU


Time zone = GMT+5 hours to the east
Long = +66.89641 deg
Lat  = +38.67332 deg 
Altitude = 2593 m
Seeing_median = 0.69"

Optical configuration: Ritchy-Chretien 
Two focal mode = a) f/7.74    <=======
                 b) f/17.34
Diameter = 1.5 m

SITe 2000x800 CCD:

full size = 2030x800 pixels
pixel size = 15 mkm 
scale = 0.266" per pixel in f/7.74   <======
        0.119" per pixel in f/17.34
field of view = 8.5x3.5 arcmin in f/7.74   <======
              = 4.0x1.6 arcmin in f/17.34
cooling agent = liquid nitrogen 
readout noise = 5.3 e- 
gain = 1.16 e-/ADU
filter set: Bessell UBVRcIc   RC   <======

"""

