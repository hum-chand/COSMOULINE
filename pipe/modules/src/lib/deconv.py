from PSF import *
from Algorithms import *
import utils as fn
import numpy as np
import time

out = fn.Verbose()

class Dec:
    def __init__(self, images, noisemaps, psf, smoothing_psf, conv_fun, 
                 img_shifts, smoothing, g_res, force_ini=False):
        #Deconv parameters:
        self.images = images
        self.noisemaps = noisemaps
        self.psf = psf
        self.psf_sm = smoothing_psf
        self.conv_fun = conv_fun
        self.shifts = img_shifts
        self.lambd = smoothing
        self.g_res = g_res
        
        #Results:
        self.model = None
        self.last_res = None
        self.ini = None
        self.trace = []
        
        #Private parameters
        self._sshape = psf.shape
        self._bshape = images[0].shape
        self._sfact = self._sshape[0]/self._bshape[0]
        self._nb_img = len(images)
        self._old_src_par = None
        
        #Initialization
        self.set_ini()
    
    def set_ini(self):
        ini = np.array([])
        for i, im in enumerate(self.images):
            ali = fn.shift(im, self.shifts[i][0]/self._sfact - self._get_offset(self.shifts[i][0]), 
                           self.shifts[i][1]/self._sfact - self._get_offset(self.shifts[i][1]), 
                           interp_order=1, mode='reflect')
            ini = append(ini, fn.rebin(ali, self._sshape)/self._sfact**2.)
        self.ini = median(ini.reshape((len(self.images), self._sshape[0]*self._sshape[1])), 
                          0).reshape(self._sshape)#/self._sfact**2.
        
    def get_im_resi(self, model_conv, im_nb):
        convo = fn.shift(model_conv, -self.shifts[im_nb][0], -self.shifts[im_nb][1], 
                       interp_order=3, mode='wrap')
#        convo = self.conv_fun(self.psf, ali)
        convo_m = fn.mean(convo, self._bshape[0], self._bshape[1])
        resi = (self.images[im_nb] - convo_m)/self.noisemaps[im_nb]
        ali_bk = fn.rebin(resi, self._sshape)/self._sfact**2.
        ali_bk = fn.shift(ali_bk, self.shifts[im_nb][0] - self._get_offset(self.shifts[im_nb][0]), 
                          self.shifts[im_nb][1] - self._get_offset(self.shifts[im_nb][1]), 
                          interp_order=3, mode='wrap')
        return ali_bk
    
    def get_err(self, model, null):
        _model = model.reshape(self._sshape)
        err = np.zeros(self._sshape, dtype=float64)
        _model_sm = self.conv_fun(self.psf_sm, _model)
#        import scipy.ndimage.filters
#        _model_sm = scipy.ndimage.filters.gaussian_laplace(_model, 3.)
        khi_smooth = self.lambd*(_model - _model_sm)**2.
        err += khi_smooth
        _model_conv = self.conv_fun(self.psf, _model)
        for i, im in enumerate(self.images):           
            khi_fit = self.get_im_resi(_model_conv, i)**2.
            err += khi_fit
        self.trace += [err.sum()]
        return err.ravel()
    
    def deconv(self, it_nb, minstep_px=None, maxstep_px=None,  stepfact=None):
        out(2, 'Begin minimization procedure')
        t = time.time()
        self.set_ini()
        minipar, lastpar = minimi(self.get_err, self.ini.ravel(),[], 
                                  minstep_px=minstep_px, maxstep_px=maxstep_px, 
                                  itnb=it_nb, stepfact=stepfact)
        self.model, self.last_res = minipar[0].reshape(self._sshape), \
                                    lastpar[0].reshape(self._sshape)
        out(2, 'Done in', time.time()-t,'[s]')
        return self.model.copy()
        
    def _get_offset(self, pos):
        return 0
        return (pos % self._sfact) - self._sfact/2.    
    

        
class DecSrc(Dec):
    def __init__(self, images, noisemaps, psf, smoothing_psf, conv_fun, img_shifts, smoothing, g_res,
                 nb_src=0, src_ini=[], src_pad=5., src_range=None, force_ini=False, 
                 max_iratio_range=None, maxpos_range=None):
        Dec.__init__(images, noisemaps, psf, smoothing_psf, conv_fun, img_shifts, smoothing, g_res, force_ini=False)
        #Source parameters:
        self.nb_src = nb_src
        self.src_ini = src_ini
        self.src_pad = src_pad
        self.src_range = src_range
        self.force_ini = force_ini
        self.max_iratio_range = max_iratio_range 
        self.maxpos_range = maxpos_range
        self.sources = [PSF(self._sshape, (self._sshape[0]/2., self._sshape[1]/2.)) 
                        for i in xrange(self._nb_img)]
        #Results:
        self.model_src = PSF(self._sshape)
        #Initialization
        if self.nb_src:
            self._set_ini_src()
    
    def get_err(self, model, srcpar):
        _model = model.reshape(self._sshape)
        srcerr = np.zeros(len(srcpar))
        if self.nb_src:
            srcerr = self._get_src_err(srcpar, _model)
            self._old_src_par = srcpar.copy()
            self._set_sources(srcpar, _model)
        err = np.zeros(self._sshape, dtype=float64)
        _model_sm = self.conv_fun(self.psf_sm, _model)
        khi_smooth = self.lambd*(_model - _model_sm)**2.
        err += khi_smooth
        for i in xrange(self._nb_img):     
            _model_conv = self.conv_fun(self.psf, _model+self.sources[i])
            khi_fit = self.get_im_resi(_model_conv, i)**2. 
            err += khi_fit
        self.trace += [err.sum()]
        return append(err, srcerr)
    
    def _set_sources(self, srcpar, bkg):
        for i in xrange(self._nb_img):
            self._add_sources(self.sources[i], srcpar, i)
    
    def _add_sources(self, im, srcpar, im_ind):
        im.reset()
        for i in xrange(self.nb_src):
            c1, c2, i0 =  srcpar[i*(2+self._nb_img)], srcpar[i*(2+self._nb_img)+1], srcpar[i*(2+self._nb_img)+2+im_ind]
            im.addGaus_fnorm_trunc(self.g_res, c1, c2, i0)
                
    def _get_src_err(self, srcpar, bkg):
        if self.max_iratio_range or self.maxpos_range:
            err = np.zeros(len(srcpar))
            #compute the error for each parameter
            for i in xrange(self._nb_img):
                #compute intensities errors
                self.sources[i].reset()
                for j in xrange(self.nb_src):
                    p_k = j*(2+self._nb_img)+2+i
                    #get the old values back
                    param = self._old_src_par.copy()
                    param[p_k] = srcpar[p_k]
                    self._add_sources(self.sources[i], param, i)
                    _model_conv = self.conv_fun(self.psf, self.sources[i] + bkg)
                    err[p_k] = (self.get_im_resi(_model_conv, i)**2.).sum()
            for i in xrange(self.nb_src):
                #compute centers errors
                #change the parameter to evaluate
                for j in xrange(2):
                    p_k = i*(2+self._nb_img) + j
                    #get the old values back
                    param = self._old_src_par.copy()
                    param[p_k] = srcpar[p_k]
                    e = 0.
                    for l in xrange(self._nb_img):
                        self.sources[i].reset()
                        self._add_sources(self.sources[l], param, l)
                        _model_conv = self.conv_fun(self.psf, self.sources[l] + bkg)
                        e += (self.get_im_resi(_model_conv, l)**2.).sum()
                    err[p_k] = e
            #return the error list 
            return abs(err)#-olderr.sum())
        else:
#            self._add_sources(srcpar, bkg)
            return [0. for s in srcpar]
        
    def _set_ini_src(self):
        import get_ini_par as init
        import wsutils as ws
        srcini =self.src_ini
        force_ini = self.force_ini
        try: 
            bkgini = fn.get_data('bkg_ini.fits')
            force_ini += (len(srcini)/3. != self.nb_src)
        except:
            force_ini = True
        if force_ini:
            out(3, 'Beginning initialization from scratch...')
            srcpos, bkgini = init._get_ini(self.ini, self.psf, self.nb_src, self.g_res, self._sfact, 
                                           self.src_range, self.conv_fun, div, self.src_pad)
            ws.drop('INI_PAR', srcini)
            fn.array2fits(bkgini, 'results/bkg_ini.fits')    
            srcini = []
            for i,p in enumerate(srcpos): 
                if i==self.nb_src or self.nb_src==0: #tmp
                    break
                srcini += [p[0],p[1]]
                for j in xrange(self._nb_img):
                    srcini += [p[2]]
        self.src_ini = np.array(srcini)
        self._old_src_par = np.array(srcini)
        self.ini = bkgini

    
class DecMC(Dec):
    def deconv(self, it_nb, minstep_px=None, maxstep_px=None,  stepfact=None, radius=None):
        out(2, 'Begin minimization procedure')
        t = time.time()
        self.set_ini()
        minipar = self._minimi_MC(self.get_err, self.ini.ravel(), itnb=it_nb)
        self.model = minipar.reshape(self._sshape)
        out(2, 'Done in', time.time()-t,'[s]')
    
    def _minimi_MC(self, func, param, itnb):
        #TODO: implement sources support
        nb_runs = 10
        par = param.copy()*3.
        std = par.std()/1000.
        lerr = (func(par,[])**2.).sum()
        for i in xrange(nb_runs):
            for j in xrange(itnb/nb_runs):
                err = []
                offs = []
                for k in xrange(2):
                    rdm = np.random.standard_normal(param.shape)
                    offset = rdm*par/50. + std*np.sign(rdm)
                    testpar = par + offset
                    err += [(func(testpar,[])**2.).sum()]
                    offs += [offset]
                ind = np.argmin(np.array(err))
                if err[ind] < lerr:
                    lerr = err[ind]
                    par += offs[ind]
                    out(3, int(100*(itnb/nb_runs*i+j+1.)/itnb), '% done.', 
                        'Error:', err[ind], '-r')
    #            if (itnb/nb_runs*i+j+1.)/itnb == 1: par += offs[ind]
            std *= 0.95
        out(3)
        return par

    
class DecPaste(Dec):
    
    def get_err(self, model, null):
        _model = model.reshape(self._sshape)
#        err = np.array(foreach(lambda i: self.get_im_resi(_model, i), 
#                               np.arange(len(self.images)), threads=len(self.images),
#                               return_=True)).sum(0)
#        err = np.array([self.get_im_resi(_model, i) for i in xrange(self._nb_img)]).sum(0)
        err = np.zeros(self._sshape, dtype=float64)
        for i in xrange(self._nb_img):           
            khi_fit = self.get_im_resi(_model, i)
            err += khi_fit
        return err.ravel()
    
    def deconv(self, it_nb, minstep, maxstep, stepfact, radius=None):
        #TODO: implement sources support
        if radius is None: radius=2.*self._sshape[0]
        if minstep is None or minstep == 0: minstep = 0.0001
        if maxstep is None or maxstep == 0: maxstep = 0.01
        mask = fn.get_circ_mask(self._sshape, radius, 1., 0.)
        model = np.zeros(self._sshape)
        self.ini = model[:]#.copy()
        err = self.get_err(model, []).reshape(self._sshape)
        chi2 = (err**2.).sum()/self._nb_img**2.
#        last_chi2 = chi2
        last_pos = -1,-1
        last_dir = -2
#        last_err = np.copy(err)*0.99
        convo = np.zeros(self._sshape, dtype=float64)
        pos = np.unravel_index((np.abs(mask*err)).argmax(), err.shape)
        step = (err[pos]/self._nb_img/self._sfact**2./self.psf.max()) /stepfact
        psf = self.conv_fun(self.psf, self.psf_sm) 
        psf /= psf
        out(2, 'Begin minimization procedure')
        t = time.time()
        for i in xrange(it_nb):#*sshape[0]**2):
            pos = np.unravel_index(np.abs(mask*err).argmax(), err.shape)
            dir = (np.sign(err[pos]))
            if pos == last_pos: 
                if dir==last_dir:
                    step *= 2.
                else:
                    step /= 4.
            else:
                step = (err[pos]/self._nb_img/self._sfact**2./self.psf.max()) /stepfact
            step = np.clip(step, minstep, maxstep)
#            step = min(step, maxstep)
#            step = max(step, minstep)
            last_dir = dir
#            last_err = np.copy(err)
            last_pos = pos
#            last_chi2 = chi2
            model[pos] += step*dir
            self._paste_psf(convo, pos, step*dir) #TODO: test (doesn't work yet)
#            convo = self.conv_fun(self.psf_sm, model)
#            khi_smooth = self.lambd*np.abs(model - convo)
            err = self.get_err(convo, []).reshape(self._sshape)#+khi_smooth
            chi2 = (err**2.).sum()/self._nb_img**2.
            self.trace += [chi2]
            out(3, 'Iteration', i+1, '- Current pos:', pos, '- Error:', chi2, '-r')
#            if chi2 > last_chi2:
#                out(3)
#                out(3, 'Increased error, exiting') 
#                break
        else:
            out(3)
        out(2, 'Done in', time.time()-t,'[s]')
        convo = self.conv_fun(self.psf_sm, model)
        self.model, self.last_res = convo, None
#        return convo, model
    
    def _paste_psf(self, dest, pos, val):
        x, y = pos
        size = self._sshape[0]
        rad = size/2.
        cr_x1 = max(x-rad, 0)
        cr_x2 = min(x+rad, size)
        cr_y1 = max(y-rad, 0)
        cr_y2 = min(y+rad, size)
        r_x1 = max(rad-x, 0)
        r_x2 = min(rad+size-x, size)
        r_y1 = max(rad-y, 0)
        r_y2 = min(rad+size-y, size)
        dest[cr_x1:cr_x2, cr_y1:cr_y2] += self.psf[r_x1:r_x2, r_y1:r_y2]*val
    
    
    