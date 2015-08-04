'''
Created on Aug 11, 2013

@author: nyga
'''
import scikits.statsmodels.api as sm
import numpy as np
import math


def weighted_linear_regression(Y, PSI, weights=None):
    '''
    Performs weighted linear regression by weighted least squares
    optimization. Computes the Moore-Penrose pseudo-inverse of the
    'design matrix' PSI, which contains the X values for the regression
    or nonlinear transformations of them according to the set of
    basis functions. Y contains the target values.
        - Y:         target values of the regression
        - PSI:       design matrix for the regression
        - weight:    vector specifying the importance of the single data points.
    '''
    if weights is None:
        weights = 1
    wls_model = sm.WLS(Y,PSI, weights=weights)
    results = wls_model.fit()
    print results.summary()
    return results.params
        

if __name__ == '__main__':
    

    def sq(x): return x ** 2
    def sine(x): return math.sin(x)  

    X = range(-5,5)
    Y = [1] * len(X) #[sq(x) for x in X]
    print Y
#     PSI = np.array([[sq(x) for x in X], [sine(x) for x in X]]).T
    PSI = np.array([[0 for x in X], [0.000000001 for x in X]]).T
    weights = [0.0000001] * (len(X)/2) + [1] * (len(X)/2)
    print PSI
    print weighted_linear_regression(Y, PSI, weights)
    
   
   
        
        
    
    
    
