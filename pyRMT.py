#!/usr/bin/env python
# -*- coding: utf-8 -*-


r"""Python for Random Matrix Theory. This package implements several 
cleaning schemes for noisy correlation matrices, including 
the optimal shrinkage, rotationally-invariant estimator
to an underlying correlation matrix (as proposed by Joel Bun, 
Jean-Philippe Bouchaud, Marc Potters and colleagues).

Such cleaned correlation matrix are known to improve factor-decomposition
via Principal Component Analysis (PCA) and could be of relevance in a variety 
of contexts, including computational biology.

Cleaning schemes also result in much improved out-of-sample risk
of Markowitz optimal portfolios, as established over the years
in several papers by Jean-Philippe Bouchaud, Marc Potters and collaborators.

Some cleaning schemes can be easily adapted from the various shrinkage
estimators implemented in the sklearn.covariance module 
(see the various publications by O. Ledoit and M. Wolf listed below).

In addition, it might make sense to perform an empirical estimate
of a correlation matrix robust to outliers before proceeding with
the cleaning schemes of the present module. Some of those robust estimates
have been implemented in the sklearn.covariance module as well. 


References
----------
* "DISTRIBUTION OF EIGENVALUES FOR SOME SETS OF RANDOM MATRICES",
  V. A. Marcenko and L. A. Pastur
  Mathematics of the USSR-Sbornik, Vol. 1 (4), pp 457-483
* "A well-conditioned estimator for large-dimensional covariance matrices",
  O. Ledoit and M. Wolf
  Journal of Multivariate Analysis, Vol. 88 (2), pp 365-411
* "Improved estimation of the covariance matrix of stock returns with "
  "an application to portfolio selection",
  O. Ledoit and M. Wolf
  Journal of Empirical Finance, Vol. 10 (5), pp 603-621
* "Financial Applications of Random Matrix Theory: a short review",
  J.-P. Bouchaud and M. Potters
  arXiv: 0910.1205 [q-fin.ST]
* "Eigenvectors of some large sample covariance matrix ensembles",
  O. Ledoit and S. Peche
  Probability Theory and Related Fields, Vol. 151 (1), pp 233-264
* "NONLINEAR SHRINKAGE ESTIMATION OF LARGE-DIMENSIONAL COVARIANCE MATRICES",
  O. Ledoit and M. Wolf
  The Annals of Statistics, Vol. 40 (2), pp 1024-1060 
* "Rotational invariant estimator for general noisy matrices",
  J. Bun, R. Allez, J.-P. Bouchaud and M. Potters
  arXiv: 1502.06736 [cond-mat.stat-mech]
* "Cleaning large Correlation Matrices: tools from Random Matrix Theory",
  J. Bun, J.-P. Bouchaud and M. Potters
  arXiv: 1610.08104 [cond-mat.stat-mech]
* "Direct Nonlinear Shrinkage Estimation of Large-Dimensional Covariance Matrices (September 2017)", 
  O. Ledoit and M. Wolf https://ssrn.com/abstract=3047302 or http://dx.doi.org/10.2139/ssrn.3047302
 
"""

from __future__ import division, print_function
from builtins import reversed
from builtins import map, zip
from collections import MutableSequence, Sequence
import copy
from math import ceil
from numbers import Complex, Integral, Real
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.covariance import EmpiricalCovariance
from sklearn.preprocessing import StandardScaler


__author__ = 'Gregory Giecold and Lionel Ouaknin'
__copyright__ = 'Copyright 2017-2022 Gregory Giecold and contributors'
__credit__ = 'Gregory Giecold and Lionel Ouaknin'
__status__ = 'beta'
__version__ = '0.1.0'


__all__ = ['clipped', 'directKernel', 'marcenkoPastur', 
           'optimalShrinkage', 'poolAdjacentViolators', 
           'stieltjes']


def checkDesignMatrix(X):
    """
       Parameters
       ----------
       X: a matrix of shape (T, N), where T denotes the number
           of samples and N labels the number of features.
           If T < N, a warning is issued to the user, and the transpose
           of X is considered instead.

       Returns:
       T: type int

       N: type int

       transpose_flag: type bool
           Specify if the design matrix X should be transposed
           in view of having less rows than columns.       
    """
    
    try:
        assert isinstance(X, (np.ndarray, pd.DataFrame, pd.Series,
                              MutableSequence, Sequence))
    except AssertionError:
        raise
        sys.exit(1)

    X = np.asarray(X, dtype=float)
    X = np.atleast_2d(X)

    if X.shape[0] < X.shape[1]:
        warnings.warn("The Marcenko-Pastur distribution pertains to "
                      "the empirical covariance matrix of a random matrix X "
                      "of shape (T, N). It is assumed that the number of "
                      "samples T is assumed higher than the number of "
                      "features N. The transpose of the matrix X submitted "
                      "at input will be considered in the cleaning schemes "
                      "for the corresponding correlation matrix.", UserWarning)
        
        T, N = reversed(X.shape)
        transpose_flag = True
    else:
        T, N = X.shape
        transpose_flag = False
        
    return T, N, transpose_flag
        
        
def marcenkoPastur(X):
    """
       Parameter
       ---------
       X: random matrix of shape (T, N), with T denoting the number
           of samples, whereas N refers to the number of features.
           It is assumed that the variance of the elements of X
           has been normalized to unity.           

       Returns
       -------
       (lambda_min, lambda_max): type tuple
           Bounds to the support of the Marcenko-Pastur distribution
           associated to random matrix X.
       rho: type function
           The Marcenko-Pastur density.

       Reference
       ---------
       "DISTRIBUTION OF EIGENVALUES FOR SOME SETS OF RANDOM MATRICES",
       V. A. Marcenko and L. A. Pastur
       Mathematics of the USSR-Sbornik, Vol. 1 (4), pp 457-483
    """

    T, N, _ = checkDesignMatrix(X)
    q = N / float(T)

    lambda_min = (1 - np.sqrt(q))**2
    lambda_max = (1 + np.sqrt(q))**2

    def rho(x):
        ret = np.sqrt((lambda_max - x) * (x - lambda_min))
        ret /= 2 * np.pi * q * x
        return ret if lambda_min < x < lambda_max else 0.0

    return (lambda_min, lambda_max), rho


def clipped(X, alpha=None, return_covariance=False):
    """Clips the eigenvalues of an empirical correlation matrix E 
       in order to provide a cleaned estimator E_clipped of the 
       underlying correlation matrix.
       Proceeds by keeping the [N * alpha] top eigenvalues and shrinking
       the remaining ones by a trace-preserving constant 
       (i.e. Tr(E_clipped) = Tr(E)).

       Parameters
       ----------
       X: design matrix, of shape (T, N), where T denotes the number
           of samples (think measurements in a time series), while N
           stands for the number of features (think of stock tickers).

       alpha: type float or derived from numbers.Real (default: None)
           Parameter between 0 and 1, inclusive, determining the fraction
           to keep of the top eigenvalues of an empirical correlation matrix.

           If left unspecified, alpha is chosen so as to keep all the
           empirical eigenvalues greater than the upper limit of 
           the support to the Marcenko-Pastur spectrum. Indeed, such 
           eigenvalues can be considered as associated with some signal,
           whereas the ones falling inside the Marcenko-Pastur range
           should be considered as corrupted with noise and indistinguishable
           from the spectrum of the correlation of a random matrix.

           This ignores finite-size effects that make it possible
           for the eigenvalues to exceed the upper and lower edges
           defined by the Marcenko-Pastur spectrum (cf. a set of results
           revolving around the Tracy-Widom distribution)
           
       return_covariance: type bool (default: False)
           If set to True, compute the standard deviations of each individual
           feature across observations, clean the underlying matrix
           of pairwise correlations, then re-apply the standard
           deviations and return a cleaned variance-covariance matrix.

       Returns
       -------
       E_clipped: type numpy.ndarray, shape (N, N)
           Cleaned estimator of the true correlation matrix C underlying
           a noisy, in-sample estimate E (empirical correlation matrix
           estimated from X). This cleaned estimator proceeds through
           a simple eigenvalue clipping procedure (cf. reference below).
           
           If return_covariance=True, E_clipped corresponds to a cleaned 
           variance-covariance matrix.

       Reference
       ---------
       "Financial Applications of Random Matrix Theory: a short review",
       J.-P. Bouchaud and M. Potters
       arXiv: 0910.1205 [q-fin.ST]
    """

    try:
        if alpha is not None:
            assert isinstance(alpha, Real) and 0 <= alpha <= 1
            
        assert isinstance(return_covariance, bool)
    except AssertionError:
        raise
        sys.exit(1)
    
    T, N, transpose_flag = checkDesignMatrix(X)
    if transpose_flag:
        X = X.T
        
    if not return_covariance:
        X = StandardScaler(with_mean=False,
                           with_std=True).fit_transform(X)

    ec = EmpiricalCovariance(store_precision=False,
                             assume_centered=True)
    ec.fit(X)
    E = ec.covariance_
    
    if return_covariance:
        inverse_std = 1./np.sqrt(np.diag(E))
        E *= inverse_std
        E *= inverse_std.reshape(-1, 1)

    eigvals, eigvecs = np.linalg.eigh(E)
    eigvecs = eigvecs.T

    if alpha is None:
        (lambda_min, lambda_max), _ = marcenkoPastur(X)
        xi_clipped = np.where(eigvals >= lambda_max, eigvals, np.nan)
    else:
        xi_clipped = np.full(N, np.nan)
        threshold = int(ceil(alpha * N))
        if threshold > 0:
            xi_clipped[-threshold:] = eigvals[-threshold:]

    gamma = float(E.trace() - np.nansum(xi_clipped))
    gamma /= np.isnan(xi_clipped).sum()
    xi_clipped = np.where(np.isnan(xi_clipped), gamma, xi_clipped)

    E_clipped = np.zeros((N, N), dtype=float)
    for xi, eigvec in zip(xi_clipped, eigvecs):
        eigvec = eigvec.reshape(-1, 1)
        E_clipped += xi * eigvec.dot(eigvec.T)
        
    tmp = 1./np.sqrt(np.diag(E_clipped))
    E_clipped *= tmp
    E_clipped *= tmp.reshape(-1, 1)
    
    if return_covariance:
      std = 1./inverse_std
      E_clipped *= std
      E_clipped *= std.reshape(-1, 1)

    return E_clipped


def stieltjes(z, E):
    """
       Parameters
       ----------
       z: complex number
       E: square matrix

       Returns
       -------
       A complex number, the resolvent of square matrix E, 
       also known as its Stieltjes transform.

       Reference
       ---------
       "Financial Applications of Random Matrix Theory: a short review",
       J.-P. Bouchaud and M. Potters
       arXiv: 0910.1205 [q-fin.ST]
    """

    try:
        assert isinstance(z, Complex)
        
        assert isinstance(E, (np.ndarray, pd.DataFrame,
                              MutableSequence, Sequence))
        E = np.asarray(E, dtype=float)
        E = np.atleast_2d(E)
        assert E.shape[0] == E.shape[1]
    except AssertionError:
        raise
        sys.exit(1)

    N = E.shape[0]
    
    ret = z * np.eye(N, dtype=float) - E
    ret = np.trace(ret) / N

    return ret


def xiHelper(x, q, E):
    """Helper function to the rotationally-invariant, optimal shrinkage
       estimator of the true correlation matrix (implemented via function
       optimalShrinkage of the present module). 

       Parameters
       ----------
       x: type derived from numbers.Real
           Would typically be expected to be an eigenvalue from the
           spectrum of correlation matrix E. The present function
           can however handle an arbitrary floating-point number.

       q: type derived from numbers.Real
           The number parametrizing a Marcenko-Pastur spectrum.

       E: type numpy.ndarray
           Symmetric correlation matrix associated with the 
           Marcenko-Pastur parameter q specified above.

       Returns
       -------
       xi: type float
           Cleaned eigenvalue of the true correlation matrix C underlying
           the empirical correlation E (the latter being corrupted 
           with in-sample noise). This cleaned version is computed
           assuming no prior knowledge on the structure of the true
           eigenvectors (thereby leaving the eigenvectors of E unscathed). 

       References
       ----------
       * "Rotational invariant estimator for general noisy matrices",
         J. Bun, R. Allez, J.-P. Bouchaud and M. Potters
         arXiv: 1502.06736 [cond-mat.stat-mech]
       * "Cleaning large Correlation Matrices: tools from Random Matrix Theory",
         J. Bun, J.-P. Bouchaud and M. Potters
         arXiv: 1610.08104 [cond-mat.stat-mech]
    """

    try:
        assert isinstance(x, Real)
        assert isinstance(q, Real)
        assert isinstance(E, np.ndarray) and E.shape[0] == E.shape[1]
        assert np.allclose(E.transpose(1, 0), E)
    except AssertionError:
        raise
        sys.exit(1)

    N = E.shape[0]
    
    z = x - 1j / np.sqrt(N)
    s = stieltjes(z, E)
    xi = x / abs(1 - q + q * z * s)**2

    return xi


def gammaHelper(x, q, N, lambda_N, inverse_wishart=False):
    """Helper function to optimalShrinkage function defined below.

       The eigenvalue to the cleaned estimator of a true correlation
       matrix are computed via the function xiHelper defined above in
       the module at hand. 
       
       It is known however that when N is not very large
       a systematic downward bias affects the xiHelper estimator for small
       eigenvalues of the noisy empirical correlation matrix. This bias
       can be heuristically corrected by computing
       xi_hat = xi_RIE * max(1, Gamma),
       with Gamma evaluated by the function gammaHelper herewith.

       Parameters
       ----------
       x: type float or any other type derived from numbers.Real
           Typically an eigenvalue from the spectrum of a sample
           estimate of the correlation matrix associated to some
           design matrix X. However, the present function supports
           any arbitrary floating-point number x at input.

       q: type derived from numbers.Real
           Parametrizes a Marcenko-Pastur spectrum.

       N: type derived from numbers.Integral
           Dimension of a correlation matrix whose debiased, 
           rotationally-invariant estimator is to be assessed via
           the function RIE (see below), of which the present function
           is a helper.

       lambda_N: type derived from numbers.Real
           Smallest eigenvalue from the spectrum of an empirical
           estimate to a correlation matrix.
        
       inverse_wishart: type bool default: False
            Wether to use inverse wishart regularization

       Returns
       ------
       Gamma: type float
           Upward correction factor for computing a debiased 
           rotationally-invariant estimator of a true underlying 
           correlation matrix. 

       Reference
       ---------
       "Cleaning large Correlation Matrices: tools from Random Matrix Theory",
        J. Bun, J.-P. Bouchaud and M. Potters
        arXiv: 1610.08104 [cond-mat.stat-mech]
    """

    try:
        assert isinstance(x, Real)
        assert isinstance(q, Real)
        assert isinstance(N, Integral)
        assert isinstance(lambda_N, Real)
    except AssertionError:
        raise
        sys.exit(1)

    z = x - 1j / np.sqrt(N)
    
    lambda_plus = (1 + np.sqrt(q))**2
    lambda_plus /= (1 - np.sqrt(q))**2
    lambda_plus *= lambda_N
    sigma_2 = lambda_N / (1 - np.sqrt(q))**2

    # gmp defined below stands for the Stieltjes transform of the
    # rescaled Marcenko-Pastur density, evaluated at z
    gmp = z + sigma_2 * (q - 1) - np.sqrt((z - lambda_N) * (z - lambda_plus))
    gmp /= 2 * q * sigma_2 * z

    Gamma = abs(1 - q + q * z * gmp)**2
    Gamma *= sigma_2
    
    if inverse_wishart:
        kappa = 2 * lambda_N / ((1 - q - lambda_N) ** 2 - 4 * q * lambda_N)
        alpha_s = 1 / (1 + 2 * q * kappa)
        denom = x / (1 + alpha_s * (x - 1.))
        Gamma /= denom
    else: 
        Gamma /= x
    
    return Gamma


def optimalShrinkage(X, return_covariance=False, method='rie'):
    """This function computes a cleaned, optimal shrinkage, 
       rotationally-invariant estimator (RIE) of the true correlation 
       matrix C underlying the noisy, in-sample estimate 
       E = 1/T X * transpose(X)
       associated to a design matrix X of shape (T, N) (T measurements 
       and N features).

       One approach to getting a cleaned estimator that predates the
       optimal shrinkage, RIE estimator consists in inverting the 
       Marcenko-Pastur equation so as to replace the eigenvalues
       from the spectrum of E by an estimation of the true ones.

       This approach is known to be numerically-unstable, in addition
       to failing to account for the overlap between the sample eigenvectors
       and the true eigenvectors. How to compute such overlaps was first
       explained by Ledoit and Peche (cf. reference below). Their procedure
       was extended by Bun, Bouchaud and Potters, who also correct
       for a systematic downward bias in small eigenvalues.
       
       It is this debiased, optimal shrinkage, rotationally-invariant
       estimator that the function at hand implements.
       
       In addition to above method, this funtion also provides access to:  
       - The finite N regularization of the optimal RIE for small eigenvalues
         as provided in section 8.1 of [3] a.k.a the inverse wishart (IW) regularization.
       - The direct kernel method of O. Ledoit and M. Wolf in their 2017 paper [4]. 
         This is a direct port of their Matlab code.
        
         
       Parameters
       ----------
       X: design matrix, of shape (T, N), where T denotes the number
           of samples (think measurements in a time series), while N
           stands for the number of features (think of stock tickers).
           
       return_covariance: type bool (default: False)
           If set to True, compute the standard deviations of each individual
           feature across observations, clean the underlying matrix
           of pairwise correlations, then re-apply the standard
           deviations and return a cleaned variance-covariance matrix.
       
       method: type string, optional (default="rie")
           - If "rie" : optimal shrinkage in the manner of Bun & al.
            with no regularisation  
           - If "iw" : optimal shrinkage in the manner of Bun & al.
            with the so called Inverse Wishart regularization
           - If 'kernel': Direct kernel method of Ledoit  Wolf.

       Returns
       -------
       E_RIE: type numpy.ndarray, shape (N, N)
           Cleaned estimator of the true correlation matrix C. A sample
           estimator of C is the empirical covariance matrix E 
           estimated from X. E is corrupted by in-sample noise.
           E_RIE is the optimal shrinkage, rotationally-invariant estimator 
           (RIE) of C computed following the procedure of Joel Bun 
           and colleagues (cf. references below).
           
           If return_covariance=True, E_clipped corresponds to a cleaned
           variance-covariance matrix.

       References
       ----------
       1 "Eigenvectors of some large sample covariance matrix ensembles",
         O. Ledoit and S. Peche
         Probability Theory and Related Fields, Vol. 151 (1), pp 233-264
       2 "Rotational invariant estimator for general noisy matrices",
         J. Bun, R. Allez, J.-P. Bouchaud and M. Potters
         arXiv: 1502.06736 [cond-mat.stat-mech]
       3 "Cleaning large Correlation Matrices: tools from Random Matrix Theory",
         J. Bun, J.-P. Bouchaud and M. Potters
         arXiv: 1610.08104 [cond-mat.stat-mech]
       4 "Direct Nonlinear Shrinkage Estimation of Large-Dimensional Covariance Matrices (September 2017)", 
         O. Ledoit and M. Wolf https://ssrn.com/abstract=3047302 or http://dx.doi.org/10.2139/ssrn.3047302
    """
    
    try:
        assert isinstance(return_covariance, bool)
    except AssertionError:
        raise
        sys.exit(1)

    T, N, transpose_flag = checkDesignMatrix(X)
    if transpose_flag:
        X = X.T
        
    if not return_covariance:
        X = StandardScaler(with_mean=False,
                           with_std=True).fit_transform(X)

    ec = EmpiricalCovariance(store_precision=False,
                             assume_centered=True)
    ec.fit(X)
    E = ec.covariance_
    
    if return_covariance:
        inverse_std = 1./np.sqrt(np.diag(E))
        E *= inverse_std
        E *= inverse_std.reshape(-1, 1)

    eigvals, eigvecs = np.linalg.eigh(E)
    eigvecs = eigvecs.T

    q = N / float(T)
    lambda_N = eigvals[0]  # The smallest empirical eigenvalue,
                           # given that the function used to compute
                           # the spectrum of a Hermitian or symmetric
                           # matrix - namely np.linalg.eigh - returns
                           # the eigenvalues in ascending order.
    lambda_hats = None
    
    if method is not 'kernel':
        use_inverse_wishart = (method == 'iw')
        xis = map(lambda x: xiHelper(x, q, E), eigvals)
        Gammas = map(lambda x: gammaHelper(x, q, N, lambda_N, inverse_wishart=use_inverse_wishart), eigvals)
        xi_hats = map(lambda a, b: a * b if b > 1 else a, xis, Gammas)
        lambda_hats = xi_hats
    else:
         lambda_hats = directKernel(q, T, N, eigvals)
        
    E_RIE = np.zeros((N, N), dtype=float)
    for lambda_hat, eigvec in zip(lambda_hats, eigvecs):
        eigvec = eigvec.reshape(-1, 1)
        E_RIE += lambda_hat * eigvec.dot(eigvec.T)
        
    tmp = 1./np.sqrt(np.diag(E_RIE))
    E_RIE *= tmp
    E_RIE *= tmp.reshape(-1, 1)
    
    if return_covariance:
        std = 1./inverse_std
        E_RIE *= std
        E_RIE *= std.reshape(-1, 1)

    return E_RIE

  
def directKernel(q, T, N, eigvals):
    """This function computes a non linear shrinkage estimator of a covariance marix
       based on the spectral distribution of its eigenvalues and that of its Hilbert Tranform.
       This is an extension of Ledoit & Péché(2011).
       
       This is a port of the Matlab code provided by O. Ledoit and M .Wolf. This port 
       uses the Pool Adjacent Violators (PAV) algorithm by Alexandre Gramfort 
       (EMAP toolbox). See below for a Python implementation of PAV.
                
       Parameters
       ----------
       q: type derived from numbers.Real
           Ratio of N/T
           
       T: type derived from numbers.Integral
          Number of samples
    
       N: type derived from numbers.Integral
           Dimension of a correlation matrix
       
       eigvals: Vector of the covariance matrix eigenvalues
       
       Returns
       -------
       dhats: A vector of eigenvalues estimates
       
       References
       ----------
       * "Eigenvectors of some large sample covariance matrix ensembles",
         O. Ledoit and S. Peche (2011)
       * "Direct Nonlinear Shrinkage Estimation of Large-Dimensional Covariance Matrices (September 2017)", 
         O. Ledoit and M. Wolf https://ssrn.com/abstract=3047302 or http://dx.doi.org/10.2139/ssrn.3047302
    """
    
    # compute direct kernel estimator
    lambdas = eigvals[max(0, N - T):].T  # transpose to have a column vector
    
    h = np.power(T, -0.35)  # Equation (5.4)
    h_squared = h ** 2
    
    L = np.matlib.repmat(lambdas, N, 1).T
    Lt = L.transpose()
    square_Lt = h_squared * (Lt ** 2)
    
    zeros = np.zeros((N, N))
    
    tmp = np.sqrt(np.maximum(4 * square_Lt - (L - Lt) ** 2, zeros)) / (2 * np.pi * square_Lt)
    f_tilde = np.mean(tmp, axis=0)    # Equation (5.2)
    
    tmp = np.sign(L - Lt) * np.sqrt(np.maximum((L - Lt) ** 2 - 4 * square_Lt, zeros)) - L + Lt 
    tmp /= 2 * np.pi * square_Lt
    Hf_tilde = np.mean(tmp, axis=1)    # Equation (5.3)
    
    if N <= T:
        tmp = (np.pi * q * lambdas * f_tilde) ** 2
        tmp += (1 - q - np.pi * q * lambdas * Hf_tilde) ** 2
        d_tilde = lambdas / tmp    # Equation (4.3)
    else:
        Hf_tilde_0 = (1 - np.sqrt(1 - 4 * h_squared)) / (2 * np.pi * h_squared) * np.mean(1. / lambdas)  # Equation (C.8)
        d_tilde_0 = 1 / (np.pi * (N - T) / T * Hf_tilde_0)  # Equation (C.5)
        d_tilde_1 = lambdas / ((np.pi ** 2) * (lambdas ** 2) * (f_tilde ** 2 + Hf_tilde ** 2))  # Equation (C.4)
        d_tilde = np.concatenate(np.dot(d_tilde_0, np.ones(N - T, 1, np.float)), d_tilde_1)
        
    d_hats = poolAdjacentViolators(d_tilde) # Equation (4.5)
    
    return d_hats

  
# Author : Alexandre Gramfort
# license : BSD
def poolAdjacentViolators(y):
    """
    PAV uses the pool adjacent violators method to produce a monotonic smoothing of y.
    Translated from matlab by Sean Collins (2006), and part of the EMAP toolbox.
    """
    
    y = np.asarray(y)
    
    try:
        assert y.ndim == 1
    except AssertionError:
      raise
      sys.exit(1)
      
    n_samples = len(y)
    v = y.copy()
    lvls = np.arange(n_samples)
    lvlsets = np.c_[lvls, lvls]
    
    while True:
        deriv = np.diff(v)
        if np.all(deriv >= 0):
            break

        violator = np.where(deriv < 0)[0]
        start = lvlsets[violator[0], 0]
        last = lvlsets[violator[0] + 1, 1]
        s = 0
        n = last - start + 1
        for i in range(start, last + 1):
            s += v[i]

        val = s / n
        for i in range(start, last + 1):
            v[i] = val
            lvlsets[i, 0] = start
            lvlsets[i, 1] = last
            
    return v

  
if __name__ == '__main__':

    pass
