#emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
#ex: set sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See the COPYING file distributed along with the PTSA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

import sys
import numpy as N
from scipy import unwrap
import scipy.stats as stats
from scipy.fftpack import fft,ifft

from ptsa.filt import decimate
from ptsa.helper import reshapeTo2D,reshapeFrom2D,nextPow2,centered
from ptsa.data import TimeSeries,Dim,Dims,DimData
from ptsa.fixed_scipy import morlet as morlet_wavelet

def morlet_multi(freqs, widths, samplerate,
                 sampling_window=7, complete=True):
    """
    Calculate Morlet wavelets with the total energy normalized to 1.
    
    Calls the scipy.signal.wavelet.morlet() function to generate
    Morlet wavelets with the specified frequencies, samplerate, and
    widths (in cycles); see the docstring for the scipy morlet function
    for details. These wavelets are normalized before they are returned.
    
    Parameters
    ----------
    freqs : {int, float, array_like of ints or floats}
        The frequencies of the Morlet wavelets.
    widths : {int, float, array_like of ints or floats}
        The width(s) of the wavelets in cycles. If only one width is passed
        in, all wavelets have the same width. If len(widths)==len(freqs),
        each frequency is paired with a corresponding width. If
        1<len(widths)<len(freqs), len(freqs) must be evenly divisible by
        len(widths) (i.e., len(freqs)%len(widths)==0). In this case widths
        are repeated such that (1/len(widths))*len(freq) neigboring wavelets
        have the same width -- e.g., if len(widths)==2, the the first and
        second half of the wavelets have widths of widths[0] and width[1]
        respectively, and if len(widths)==3 the first, middle, and last
        third of wavelets have widths of widths[0], widths[1], and widths[2]
        respectively.
    samplerate : {float}
        The sample rate of the signal (e.g., 200 Hz).
    sampling_window : {float},optional
        How much of the wavelet is sampled. As sampling_window increases,
        the number of samples increases and thus the samples near the edge
        approach zero increasingly closely. The number of samples are
        determined from the wavelet(s) with the largest standard deviation
        in the time domain. All other wavelets are therefore guaranteed to
        approach zero better at the edges. A value >= 7 is recommended.
    complete : {bool},optional
        Whether to generate a complete or standard approximation to
        the complete version of a Morlet wavelet. Complete should be True,
        especially for low (<=5) values of width. See
        scipy.signal.wavelet.morlet() for details.
    
    Returns
    -------
    A 2-D (frequencies * samples) array of Morlet wavelets.
    
    Notes
    -----
    The in scipy versions <= 0.6.0, the scipy.signal.wavelet.morlet()
    code contains a bug. Until it is fixed in a stable release, this
    code calls a local fixed version of the scipy function.
    
    Examples
    --------
    >>> wavelet = morlet_multi(10,5,200)
    >>> wavelet.shape
    (1, 112)
    >>> wavelet = morlet_multi([10,20,30],5,200)
    >>> wavelet.shape
    (3, 112)
    >>> wavelet = morlet_multi([10,20,30],[5,6,7],200)
    >>> wavelet.shape
    (3, 112)
    """
    # ensure the proper dimensions
    freqs = N.atleast_1d(freqs)
    widths = N.atleast_1d(widths)

    # make len(widths)==len(freqs):
    widths = widths.repeat(len(freqs)/len(widths))
    if len(widths) != len(freqs):
        raise ValueError("Freqs and widths are not compatible: len(freqs) must "+
                         "be evenly divisible by len(widths).\n"+
                         "len(freqs) = "+str(len(freqs))+"\nlen(widths) = "+
                         str(len(widths)/(len(freqs)/len(widths))))
    
    # std. devs. in the time domain:
    st = widths/(2*N.pi*freqs)
    
    # determine number of samples needed based on wavelet with maximum
    # standard deviation in time domain
    samples = N.ceil(N.max(st)*samplerate*sampling_window)
    
    # determine the scales of the wavelet (cf.
    # scipy.signal.wavelets.morlet docstring):
    scales = (freqs*samples)/(2.*widths*samplerate)
    
    #wavelets = N.empty((len(freqs),samples),dtype=N.complex128)
    wavelets = N.empty((len(freqs),samples),dtype=N.complex)
    for i in xrange(len(freqs)):
        wavelets[i] = morlet_wavelet(samples,w=widths[i],s=scales[i],
                                     complete=complete)
    #wavelets = N.array([morlet_wavelet(samples,w=widths[i],s=scales[i],
    #                                   complete=complete)
    #                    for i in xrange(len(scales))])
    energy = N.sqrt(N.sum(N.power(N.abs(wavelets),2.),axis=1)/samplerate)
    norm_factors = N.vstack([1./energy]*samples).T
    return wavelets*norm_factors


def morlet_multi2(freqs, widths, samplerate,fft_thresh=90,
                 sampling_window=7, complete=True):
    """
    Calculate Morlet wavelets with the total energy normalized to 1.
    
    Calls the scipy.signal.wavelet.morlet() function to generate
    Morlet wavelets with the specified frequencies, samplerate, and
    widths (in cycles); see the docstring for the scipy morlet function
    for details. These wavelets are normalized before they are returned.
    
    Parameters
    ----------
    freqs : {int, float, array_like of ints or floats}
        The frequencies of the Morlet wavelets.
    widths : {int, float, array_like of ints or floats}
        The width(s) of the wavelets in cycles. If only one width is passed
        in, all wavelets have the same width. If len(widths)==len(freqs),
        each frequency is paired with a corresponding width. If
        1<len(widths)<len(freqs), len(freqs) must be evenly divisible by
        len(widths) (i.e., len(freqs)%len(widths)==0). In this case widths
        are repeated such that (1/len(widths))*len(freq) neigboring wavelets
        have the same width -- e.g., if len(widths)==2, the the first and
        second half of the wavelets have widths of widths[0] and width[1]
        respectively, and if len(widths)==3 the first, middle, and last
        third of wavelets have widths of widths[0], widths[1], and widths[2]
        respectively.
    samplerate : {float}
        The sample rate of the signal (e.g., 200 Hz).
    fft_thresh : {int},optional
        The number of samples above which to switch to FFT convolution.
    sampling_window : {float},optional
        How much of the wavelet is sampled. As sampling_window increases,
        the number of samples increases and thus the samples near the edge
        approach zero increasingly closely. The number of samples are
        determined from the wavelet(s) with the largest standard deviation
        in the time domain. All other wavelets are therefore guaranteed to
        approach zero better at the edges. A value >= 7 is recommended.
    complete : {bool},optional
        Whether to generate a complete or standard approximation to
        the complete version of a Morlet wavelet. Complete should be True,
        especially for low (<=5) values of width. See
        scipy.signal.wavelet.morlet() for details.
    
    Returns
    -------
    A 2-D (frequencies * samples) array of Morlet wavelets.
    
    Notes
    -----
    The in scipy versions <= 0.6.0, the scipy.signal.wavelet.morlet()
    code contains a bug. Until it is fixed in a stable release, this
    code calls a local fixed version of the scipy function.
    
    Examples
    --------
    >>> wavelet = morlet_multi(10,5,200)
    >>> wavelet.shape
    (1, 112)
    >>> wavelet = morlet_multi([10,20,30],5,200)
    >>> wavelet.shape
    (3, 112)
    >>> wavelet = morlet_multi([10,20,30],[5,6,7],200)
    >>> wavelet.shape
    (3, 112)
    """
    # ensure the proper dimensions
    freqs = N.atleast_1d(freqs)
    widths = N.atleast_1d(widths)

    # make len(widths)==len(freqs):
    widths = widths.repeat(len(freqs)/len(widths))
    if len(widths) != len(freqs):
        raise ValueError("Freqs and widths are not compatible: len(freqs) must "+
                         "be evenly divisible by len(widths).\n"+
                         "len(freqs) = "+str(len(freqs))+"\nlen(widths) = "+
                         str(len(widths)/(len(freqs)/len(widths))))
    
    # std. devs. in the time domain:
    st = widths/(2*N.pi*freqs)
    
    # determine number of samples needed based on wavelet with maximum
    # standard deviation in time domain
    samples = N.ceil(st*samplerate*sampling_window)
    #samples = N.ceil(N.max(st)*samplerate*sampling_window)

    # get indices for wavelets that exceed the threshold for fft
    # convolution:
    fft_ind = N.array(samples > fft_thresh)
    if fft_ind.any():
        fft_samples = N.max(samples[fft_ind])
        fft_freqs = freqs[fft_ind]
        fft_widths = widths[fft_ind]
    
        # determine the scales of the wavelet (cf.
        # scipy.signal.wavelets.morlet docstring):
        fft_scales = (fft_freqs*fft_samples)/(2.*fft_widths*samplerate)
        
        #fft_wavelets = N.empty((len(fft_freqs),fft_samples),dtype=N.complex128)
        fft_wavelets = N.empty((len(fft_freqs),fft_samples),dtype=N.complex)
        for i in xrange(len(fft_freqs)):
            fft_wavelets[i] = morlet_wavelet(fft_samples,w=fft_widths[i],
                                             s=fft_scales[i],complete=complete)
        fft_energy = N.sqrt(N.sum(N.power(N.abs(fft_wavelets),2.),
                                  axis=1)/samplerate)
        fft_norm_factors = N.vstack([1./fft_energy]*fft_samples).T
        fft_wavelets = fft_wavelets*fft_norm_factors
    else:
        fft_wavelets = N.array([[]])
        
    reg_samples = samples[~fft_ind]
    reg_freqs = freqs[~fft_ind]
    reg_widths = widths[~fft_ind]
    
    reg_scales = (reg_freqs*reg_samples)/(2.*reg_widths*samplerate)

    reg_wavelets = [morlet_wavelet(reg_samples[i],w=reg_widths[i],
                                   s=reg_scales[i],complete=complete)
                    for i in xrange(len(reg_scales))]
    reg_energy = [N.sqrt(N.sum(N.power(N.abs(reg_wavelets[i]),2.))/samplerate)
                  for i in xrange(len(reg_scales))]
    reg_norm_wavelets = [reg_wavelets[i]/reg_energy[i]
                         for i in xrange(len(reg_scales))]

    return (fft_wavelets,reg_norm_wavelets,fft_ind)


def fconv_multi(in1, in2, mode='full'):
    """
    Convolve multiple 1-dimensional arrays using FFT.

    Calls scipy.signal.fft on every row in in1 and in2, multiplies
    every possible pairwise combination of the transformed rows, and
    returns an inverse fft (by calling scipy.signal.ifft) of the
    result. Therefore the output array has as many rows as the product
    of the number of rows in in1 and in2 (the number of colums depend
    on the mode).
    
    Parameters
    ----------
    in1 : {array_like}
        First input array. Must be arranged such that each row is a
        1-D array with data to convolve.
    in2 : {array_like}
        Second input array. Must be arranged such that each row is a
        1-D array with data to convolve.
    mode : {'full','valid','same'},optional
        Specifies the size of the output. See the docstring for
        scipy.signal.convolve() for details.
    
    Returns
    -------
    Array with in1.shape[0]*in2.shape[0] rows with the convolution of
    the 1-D signals in the rows of in1 and in2.
    """    
    # ensure proper number of dimensions
    in1 = N.atleast_2d(in1)
    in2 = N.atleast_2d(in2)

    # get the number of signals and samples in each input
    num1,s1 = in1.shape
    num2,s2 = in2.shape
    
    # see if we will be returning a complex result
    complex_result = (N.issubdtype(in1.dtype, N.complex) or
                      N.issubdtype(in2.dtype, N.complex))

    # determine the size based on the next power of 2
    actual_size = s1+s2-1
    size = N.power(2,nextPow2(actual_size))

    # perform the fft of each row of in1 and in2:
    #in1_fft = N.empty((num1,size),dtype=N.complex128)
    in1_fft = N.empty((num1,size),dtype=N.complex)
    for i in xrange(num1):
        in1_fft[i] = fft(in1[i],size)
    #in2_fft = N.empty((num2,size),dtype=N.complex128)
    in2_fft = N.empty((num2,size),dtype=N.complex)
    for i in xrange(num2):
        in2_fft[i] = fft(in2[i],size)
    
    # duplicate the signals and multiply before taking the inverse
    in1_fft = in1_fft.repeat(num2,axis=0)
    in1_fft *= N.vstack([in2_fft]*num1)
    ret = ifft(in1_fft)
#     ret = ifft(in1_fft.repeat(num2,axis=0) * \
#                N.vstack([in2_fft]*num1))
    
    # delete to save memory
    del in1_fft, in2_fft
    
    # strip of extra space if necessary
    ret = ret[:,:actual_size]
    
    # determine if complex, keeping only real if not
    if not complex_result:
        ret = ret.real
    
    # now only keep the requested portion
    if mode == "full":
        return ret
    elif mode == "same":
        if s1 > s2:
            osize = s1
        else:
            osize = s2
        return centered(ret,(num1*num2,osize))
    elif mode == "valid":
        return centered(ret,(num1*num2,N.abs(s2-s1)+1))


def phase_pow_multi(freqs, dat, samplerate, widths=5, to_return='both',
                    time_axis=-1, freq_axis=0, **kwargs):
    """
    Calculate phase and power with wavelets across multiple events.

    Calls the morlet_multi() and fconv_multi() functions to convolve
    dat with Morlet wavelets.  Phase and power over time across all
    events are calculated from the results. Time/samples should
    include a buffer before onsets and after offsets of the events of
    interest to avoid edge effects.

    Parameters
    ----------
    freqs : {int, float, array_like of ints or floats}
        The frequencies of the Morlet wavelets.
    dat : {array_like}
        The data to determine the phase and power of. Time/samples must be
        last dimension and should include a buffer to avoid edge effects.
    samplerate : {float}
        The sample rate of the signal (e.g., 200 Hz).
    widths : {int, float, array_like of ints or floats}
        The width(s) of the wavelets in cycles. See docstring of
        morlet_multi() for details.
    to_return : {'both','power','phase'}, optional
        Specify whether to return power, phase, or both.
    time_axis : {int},optional
        Index of the time/samples dimension in dat.
        Should be in {-1,0,len(dat.shape)}
    freq_axis : {int},optional
        Index of the frequency dimension in the returned array(s).
        Should be in {0, time_axis, time_axis+1,len(dat.shape)}.
    **kwargs : {**kwargs},optional
        Additional key word arguments to be passed on to morlet_multi().
    
    Returns
    -------
    Array(s) of phase and/or power values as specified in to_return. The
    returned array(s) has/have one more dimension than dat. The added
    dimension is for the frequencies and is inserted at freq_axis.
    """
    if to_return != 'both' and to_return != 'power' and to_return != 'phase':
        raise ValueError("to_return must be \'power\', \'phase\', or \'both\' to "+
                         "specify whether power, phase, or both are to be "+
                         "returned. Invalid value: %s " % to_return)

    # generate array of wavelets:
    wavelets = morlet_multi(freqs,widths,samplerate,**kwargs)

    # make sure we have at least as many data samples as wavelet samples
    if wavelets.shape[1]>dat.shape[time_axis]:
        raise ValueError("The number of data samples is insufficient compared "+
                         "to the number of wavelet samples. Try increasing "+
                         "data samples by using a (longer) buffer.\n data "+
                         "samples: "+str(dat.shape[time_axis])+"\nwavelet "+
                         "samples: "+str(wavelets.shape[1]))
    
    # reshape the data to 2D with time on the 2nd dimension
    origshape = dat.shape
    eegdat = reshapeTo2D(dat,time_axis)

    # calculate wavelet coefficients:
    wavCoef = fconv_multi(wavelets,eegdat,mode='same')

    # Determine shape for ouput arrays with added frequency dimension:
    newshape = list(origshape)
    # freqs must be first for reshapeFrom2D to work
    # XXX
    newshape.insert(freq_axis,len(freqs))
    newshape = tuple(newshape)
    
    if to_return == 'power' or to_return == 'both':
        # calculate power:
        power = N.power(N.abs(wavCoef),2)
        # reshape to new shape:
        power = reshapeFrom2D(power,time_axis,newshape)

    if to_return == 'phase' or to_return == 'both':
        # normalize the phase estimates to length one taking care of
        # instances where they are zero:
        norm_factor = N.abs(wavCoef)
        ind = norm_factor == 0
        norm_factor[ind] = 1.
        wavCoef = wavCoef/norm_factor
        wavCoef[ind] = 0
        # calculate phase:
        phase = N.angle(wavCoef)
        # reshape to new shape
        phase = reshapeFrom2D(phase,time_axis,newshape)

    if to_return == 'power':
        return power
    elif to_return == 'phase':
        return phase
    elif to_return == 'both':
        return phase,power
    

def phase_pow_multi2(freqs, dat, samplerate, widths=5, to_return='both',
                    time_axis=-1, freq_axis=0, **kwargs):
    """
    Calculate phase and power with wavelets across multiple events.

    Calls the morlet_multi() and fconv_multi() functions to convolve
    dat with Morlet wavelets.  Phase and power over time across all
    events are calculated from the results. Time/samples should
    include a buffer before onsets and after offsets of the events of
    interest to avoid edge effects.

    Parameters
    ----------
    freqs : {int, float, array_like of ints or floats}
        The frequencies of the Morlet wavelets.
    dat : {array_like}
        The data to determine the phase and power of. Time/samples must be
        last dimension and should include a buffer to avoid edge effects.
    samplerate : {float}
        The sample rate of the signal (e.g., 200 Hz).
    widths : {int, float, array_like of ints or floats}
        The width(s) of the wavelets in cycles. See docstring of
        morlet_multi() for details.
    to_return : {'both','power','phase'}, optional
        Specify whether to return power, phase, or both.
    time_axis : {int},optional
        Index of the time/samples dimension in dat.
        Should be in {-1,0,len(dat.shape)}
    freq_axis : {int},optional
        Index of the frequency dimension in the returned array(s).
        Should be in {0, time_axis, time_axis+1,len(dat.shape)}.
    **kwargs : {**kwargs},optional
        Additional key word arguments to be passed on to morlet_multi().
    
    Returns
    -------
    Array(s) of phase and/or power values as specified in to_return. The
    returned array(s) has/have one more dimension than dat. The added
    dimension is for the frequencies and is inserted at freq_axis.
    """
    if to_return != 'both' and to_return != 'power' and to_return != 'phase':
        raise ValueError("to_return must be \'power\', \'phase\', or \'both\' to "+
                         "specify whether power, phase, or both are to be "+
                         "returned. Invalid value: %s " % to_return)

    # generate array of wavelets:
    fft_wavelets,reg_wavelets,fft_ind = morlet_multi2(freqs,widths,samplerate,
                                                     **kwargs)
    # make sure we have at least as many data samples as wavelet samples
    if ((fft_wavelets.shape[1] > dat.shape[time_axis]) or
        ((len(reg_wavelets)>0) and
        (N.max([len(i) for i in reg_wavelets]) >  dat.shape[time_axis]))):
        raise ValueError("The number of data samples is insufficient compared "+
                         "to the number of wavelet samples. Try increasing "+
                         "data samples by using a (longer) buffer.\n data "+
                         "samples: "+str(dat.shape[time_axis])+"\nwavelet "+
                         "samples: "+str(fft_wavelets.shape[1]))
    
    # reshape the data to 2D with time on the 2nd dimension
    origshape = dat.shape
    eegdat = reshapeTo2D(dat,time_axis)

    # calculate wavelet coefficients:
    #wavCoef = N.empty((eegdat.shape[time_axis-1]*len(freqs),
    #                   eegdat.shape[time_axis]),dtype=N.complex128)
    wavCoef = N.empty((eegdat.shape[time_axis-1]*len(freqs),
                       eegdat.shape[time_axis]),dtype=N.complex)
    if fft_wavelets.shape[1] > 0:
        fconv_ind = N.repeat(fft_ind,eegdat.shape[time_axis-1])
        wavCoef[fconv_ind] = fconv_multi(fft_wavelets,eegdat,mode='same')

    #reg_wavCoef = N.empty((eegdat.shape[time_axis-1]*N.sum(~fft_ind),
    #                       eegdat.shape[time_axis]),dtype=N.complex128)
    reg_wavCoef = N.empty((eegdat.shape[time_axis-1]*N.sum(~fft_ind),
                           eegdat.shape[time_axis]),dtype=N.complex)
    conv_ind = N.repeat(~fft_ind,eegdat.shape[time_axis-1])
    i=0
    for reg in xrange(len(reg_wavelets)):
        for ev,evDat in enumerate(dat):
            #print len(reg_wavelets), reg
            reg_wavCoef[i] = N.convolve(reg_wavelets[reg],evDat,'same')
            i += 1
    wavCoef[conv_ind] = reg_wavCoef
    
    # Determine shape for ouput arrays with added frequency dimension:
    newshape = list(origshape)
    # freqs must be first for reshapeFrom2D to work
    # XXX
    newshape.insert(freq_axis,len(freqs))
    newshape = tuple(newshape)
    
    if to_return == 'power' or to_return == 'both':
        # calculate power:
        power = N.power(N.abs(wavCoef),2)
        # reshape to new shape:
        power = reshapeFrom2D(power,time_axis,newshape)

    if to_return == 'phase' or to_return == 'both':
        # normalize the phase estimates to length one taking care of
        # instances where they are zero:
        norm_factor = N.abs(wavCoef)
        ind = norm_factor == 0
        norm_factor[ind] = 1.
        wavCoef = wavCoef/norm_factor
        wavCoef[ind] = 0
        # calculate phase:
        phase = N.angle(wavCoef)
        # reshape to new shape
        phase = reshapeFrom2D(phase,time_axis,newshape)

    if to_return == 'power':
        return power
    elif to_return == 'phase':
        return phase
    elif to_return == 'both':
        return phase,power



##################
# Old wavelet code
##################

def morlet(freq,t,width):
    """Generate a Morlet wavelet for specified frequncy for times t.
    The wavelet will be normalized so the total energy is 1.  width
    defines the ``width'' of the wavelet in cycles.  A value >= 5 is
    suggested.
    """
    sf = float(freq)/float(width)
    st = 1./(2*N.pi*sf)
    A = 1./N.sqrt(st*N.sqrt(N.pi))
    y = A*N.exp(-N.power(t,2)/(2*N.power(st,2)))*N.exp(2j*N.pi*freq*t)
    return y


def phasePow1d(freq,dat,samplerate,width):
    """ Calculate phase and power for a single freq and 1d signal.

    """
    # set the parameters for the wavelet
    dt = 1./float(samplerate)
    sf = float(freq)/float(width)
    st = 1./(2*N.pi*sf)
    
    # get the morlet wavelet for the proper time range
    t=N.arange(-3.5*st,3.5*st,dt)
    m = morlet(freq,t,width)

    # make sure we are not trying to get a too low a freq
    # for now it is up to them
    #if len(t) > len(dat):
	#raise

    # convolve the wavelet and the signal
    y = N.convolve(m,dat,'full')

    # cut off the extra
    y = y[N.ceil(len(m)/2.)-1:len(y)-N.floor(len(m)/2.)];

    # get the power
    power = N.power(N.abs(y),2)

    # find where the power is zero
    ind = power==0
        
    # normalize the phase estimates to length one
    y[ind] = 1.
    y = y/N.abs(y)
    y[ind] = 0
        
    # get the phase
    phase = N.angle(y)

    return phase,power

def phasePow2d(freq,dat,samplerate,width):
    """ Calculate phase and power for a single freq and 2d signal of shape
    (events,time).

    This will be slightly faster than phasePow1d for multiple events
    because it only calculates the Morlet wavelet once.  """
    # set the parameters for the wavelet
    dt = 1./float(samplerate)
    sf = float(freq)/float(width)
    st = 1./(2*N.pi*sf)
    
    # get the morlet wavelet for the proper time range
    t=N.arange(-3.5*st,3.5*st,dt)
    m = morlet(freq,t,width)

    # make sure is array
    dat = N.asarray(dat)

    # allocate for the necessary space
    #wCoef = N.empty(dat.shape,N.complex64)
    wCoef = N.empty(dat.shape,N.complex128)

    for ev,evDat in enumerate(dat):
	# convolve the wavelet and the signal
	y = N.convolve(m,evDat,'full')

	# cut off the extra
	y = y[N.ceil(len(m)/2.)-1:len(y)-N.floor(len(m)/2.)];

	# insert the data
	wCoef[ev] = y

    # get the power
    power = N.power(N.abs(wCoef),2)

    # find where the power is zero
    ind = power==0
        
    # normalize the phase estimates to length one
    wCoef[ind] = 1.
    wCoef = wCoef/N.abs(wCoef)
    wCoef[ind] = 0
        
    # get the phase
    phase = N.angle(wCoef)

    return phase,power

def tsPhasePow(freqs,tseries,width=5,resample=None,keepBuffer=False,
               verbose=False,to_return='both',freqDimName='freq'):
    """
    Calculate phase and/or power on an TimeSeries, returning new
    TimeSeries instances.
    """
    if (to_return != 'both') and (to_return != 'pow') and (to_return != 'phase'):
        raise ValueError("to_return must be \'pow\', \'phase\', or \'both\' to\
        specify whether power, phase, or both should be  returned. Invalid\
        value for to_return: %s " % to_return)
    
    # first get the phase and power as desired
    res = calcPhasePow(freqs,tseries.data,tseries.samplerate,axis=tseries.tdim,
                       width=width,verbose=verbose,to_return=to_return)

    # handle the dims
    tsdims = tseries.dims.copy()

    # add in frequency dimension
    freqDim = Dim(freqDimName,freqs,'Hz')
    tsdims.insert(0,freqDim)
    
    # turn them into timeseries
    if to_return == 'pow' or to_return == 'both':
        # turn into a timeseries
        powerAll = TimeSeries(res,tsdims,
                              tseries.samplerate,unit='XXX get pow unit',
                              tdim=-1,buf_samp=tseries.buf_samp)
        powerAll.data[powerAll.data<=0] = N.finfo(powerAll.data.dtype).eps
        # see if resample
        if resample:
            # must take log before the resample
            powerAll.data = N.log10(powerAll.data)
            powerAll.resample(resample)
            powerAll.data = N.power(10,powerAll.data)
        # see if remove buffer
        if not keepBuffer:
            powerAll.removeBuf()
    
    if to_return == 'phase' or to_return == 'both':
        # get the phase matrix
        phaseAll = TimeSeries(res,tsdims,
                              tseries.samplerate,unit='radians',
                              tdim=-1,buf_samp=tseries.buf_samp)
        if resample:
            # must unwrap before resampling
            phaseAll.data = N.unwrap(phaseAll.data)
            phaseAll.resample(resample)
            phaseAll.data = N.mod(phaseAll.data+N.pi,2*N.pi)-N.pi;            
        # see if remove buffer
        if not keepBuffer:
            phaseAll.removeBuf()
    
    # see what to return
    if to_return == 'pow':
        return powerAll
    elif to_return == 'phase':
        return phaseAll
    elif to_return == 'both':
        return phaseAll,powerAll
        
    

def calcPhasePow(freqs,dat,samplerate,axis=-1,width=5,verbose=False,to_return='both'):
    """Calculate phase and power over time with a Morlet wavelet.

    You can optionally pass in downsample, which is the samplerate to
    decimate to following the power/phase calculation. 

    As always, it is best to pass in extra signal (a buffer) on either
    side of the signal of interest because power calculations and
    decimation have edge effects."""

    if to_return != 'both' and to_return != 'pow' and to_return != 'phase':
        raise ValueError("to_return must be \'pow\', \'phase\', or \'both\' to specify whether power, phase, or both are returned. Invalid value: %s " % to_return)
    
    # reshape the data to 2D with time on the 2nd dimension
    origshape = dat.shape
    eegdat = reshapeTo2D(dat,axis)

    # allocate
    phaseAll = []
    powerAll = []

    # loop over freqs
    freqs = N.asarray(freqs)
    if len(freqs.shape)==0:
	freqs = N.array([freqs])
    if verbose:
	sys.stdout.write('Calculating wavelet phase/power...\n')
	sys.stdout.write('Freqs (%g to %g): ' % (N.min(freqs),N.max(freqs)))
    for f,freq in enumerate(freqs):
	if verbose:
	    sys.stdout.write('%g ' % (freq))
	    sys.stdout.flush()
	# get the phase and power for that freq
	phase,power = phasePow2d(freq,eegdat,samplerate,width)
        
        # reshape back do original data shape
	if to_return == 'phase' or to_return == 'both':
	    phase = reshapeFrom2D(phase,axis,origshape)
	if to_return == 'pow' or to_return == 'both':
	    power = reshapeFrom2D(power,axis,origshape)

	# see if allocate
	if len(phaseAll) == 0 and len(powerAll) == 0:
	    if to_return == 'phase' or to_return == 'both':
		phaseAll = N.empty(N.concatenate(([len(freqs)],phase.shape)),
				   dtype=phase.dtype)
	    if to_return == 'pow' or to_return == 'both':
		powerAll = N.empty(N.concatenate(([len(freqs)],power.shape)),
				   dtype=power.dtype)
        # insert into all
	if to_return == 'phase' or to_return == 'both':
	    phaseAll[f] = phase
	if to_return == 'pow' or to_return == 'both':
	    powerAll[f] = power

    if verbose:
	sys.stdout.write('\n')

    if to_return == 'pow':
        return powerAll
    elif to_return == 'phase':
        return phaseAll
    elif to_return == 'both':
        return phaseAll,powerAll


