#
#    Copyright (C) <2013>  <cummings.evan@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from pylab                   import *
from scipy.optimize          import fminbound
from scipy.sparse.linalg     import cg
from Inverse_System          import *
from mpl_toolkits.axes_grid1 import make_axes_locatable
from functions               import descritize_PSF_kernel as d_psf
from functions               import descritize_integral   as d_int

class Inverse_System_2D(Inverse_System):

  def __init__(self, sig, err_lvl, x_true, PSF, recon=False, cmap='Greys',
               per_BC=False, per_BC_pad=False, per_t=0.0, 
               restrict_dom=(None,None)):
    """
    class representing a system we wish to invert.
    INPUT:
      sig          - x_true_ftn parameter.
      err_lvl      - desired noise level (ratio of 100).
      x_true       - function from functions.py representing the true solution.
      PSF          - Point Spread Function.
      recon        - weather or not this is a PSF reconstruction problem. 
      cmap         - matplotlib colormap string name.
      per_BC       - use periodic boundary condtions?
      per_BC_pad   - pad the image to apply periodic BC without distortion?
      per_t        - truncate amount (left, right, top, and bottom).
      restrict_dom - 2-tuple index to restrict (left, right) = (top, bottom) 
    """
    super(Inverse_System_2D, self).__init__()
    self.per_BC     = per_BC
    self.per_BC_pad = per_BC_pad

    nx, ny  = shape(x_true)
    nx      = float(nx)
    ny      = float(ny)
    n       = nx * ny
    hx      = 1/nx
    hy      = 1/ny

    if not per_BC:
      tx      = arange(0, 1, hx)
      ty      = arange(0, 1, hy)
      # A discritization :
      if not recon:
        A1       = d_psf(tx, hx, PSF(tx, hx, sig=sig))
        A2       = d_psf(ty, hy, PSF(ty, hy, sig=sig))
      else:
        A1       = d_int(tx, hx)
        A2       = d_int(ty, hy)

      # Set up true solution x_true and data b = A*x_true + error :
      Ax      = dot(dot(A1, x_true), A2.T)
      sigma   = err_lvl/100.0 * norm(Ax) / sqrt(n)
      eta     = sigma * randn(nx, ny)
      b       = Ax + eta
   
      U1,S1,V1 = svd(A1)
      U2,S2,V2 = svd(A2)
      S        = tensordot(S2, S1, 0)
      UTb      = dot(dot(U1.T, b), U2)
      Vx       = dot(V1.T, dot(x_true, V2))
      
      self.A1  = A1
      self.A2  = A2
      self.U1  = U1
      self.U2  = U2
      self.V1  = V1
      self.V2  = V2
      self.S1  = S1
      self.S2  = S2
    
    else:
      left    = -per_t
      right   =  per_t
      bottom  = -per_t
      top     =  per_t
      tx      = arange(left,   right, hx)
      ty      = arange(bottom, top,   hy)
      
      # A discritization :
      if not recon:
        X,Y      = meshgrid(tx,ty)
        ahat     = fft2(fftshift(PSF(X, Y, hx, hy, sig=sig)))
      else:
        print "reconstruction not implemented"
        exit(1)

      # Set up true solution x_true and data b = A*x_true + error :
      l       = restrict_dom[0]
      r       = restrict_dom[1]
      Ax      = real(ifft2(ahat * fft2(x_true)))
      Ax      = Ax[l:r, l:r]
      x_true  = x_true[l:r, l:r]
      nx2,ny2 = shape(Ax)
      nx2     = float(nx2)
      ny2     = float(ny2)
      n2      = nx2 * ny2
      sigma   = err_lvl/100.0 * norm(Ax) / sqrt(n2)
      eta     = sigma * randn(nx2, ny2)
      b       = Ax + eta
      bhat    = fft2(b)
     
      if self.per_BC_pad:
        p_d   = ((ny/4, ny/4), (nx/4, nx/4))
        b_pad = pad(b, p_d, 'constant')
        bphat = fft2(b_pad)
        DT    = pad(ones(ny2), (ny/4, ny/4), 'constant')
        D     = pad(ones(nx2), (nx/4, nx/4), 'constant')
        M     = tensordot(DT, D, 0) # mask array
        ATDb  = real(ifft2(conj(ahat) * fft2(b_pad)))
        UTb   = bphat

        self.D     = D
        self.DT    = DT
        self.M     = M
        self.ATDb  = ATDb
        self.bphat = bphat
        self.b_pad = b_pad

      else:
        if l is not None and r is not None:
          ml = 0.5*(r - l)
          mr = 1.5*(r - l)
        else:
          ml = 0
          mr = nx
        ahat  = ahat[ml:mr, ml:mr]
        UTb   = bhat
        
      S       = abs(ahat)
      Vx      = fft2(x_true)

      self.ahat = ahat
    
    # 2D problems can only be filtered by Tikhonov regularization
    self.filt_type = 'Tikhonov'
    
    self.cmap        = cmap
    self.per_BC      = per_BC
    self.per_BC_pad  = per_BC_pad
    self.rng         = arange(0, 1, 0.1)
    self.n           = n
    self.nx          = nx
    self.ny          = ny
    self.tx          = tx
    self.ty          = ty
    self.x_true      = x_true
    self.Ax          = Ax
    self.err_lvl     = err_lvl
    self.sigma       = sigma
    self.b           = b
    self.S           = S
    self.UTb         = UTb
    self.Vx          = Vx

  def get_xfilt(self, alpha=None):
    """
    get the filtered x solution.
    """
    S      = self.S
    UTb    = self.UTb
    # if not periodic boundary conditions:
    if not self.per_BC:
      V1     = self.V1
      V2     = self.V2
      if self.filt_type == 'Tikhonov':
        dSfilt = S**2 / (S**2 + alpha) 
      else:
        dSfilt         = ones((self.nx, self.ny))
        dSfilt[alpha:] = 0.0
      x_filt = dot(V1.T, dot(dSfilt / S * UTb, V2))
    # else periodic boundary :
    else:
      # if we do not pad the image :
      if not self.per_BC_pad:
        if self.filt_type == 'Tikhonov':
          dSfilt = S**2 / (S**2 + alpha) 
        elif self.filt_type == 'Landweber':
          pass
        else:
          dSfilt         = ones((self.nx, self.ny))
          dSfilt[alpha:] = 0.0
        x_filt = real(ifft2(dSfilt / S * UTb))
      # else we pad :
      else:
        if self.filt_type == 'Landweber':
          ATDb  = self.ATDb
          M     = self.M
          ahat  = self.ahat
          bphat = self.bphat
          b     = self.b
          sig   = self.sigma
          tau   = self.tau

          # conjugate gradient garbage :
          #MA    = M * real(ifft2(ahat))
          #ATMA  = real(ifft2(conj(ahat) * fft2(MA)))
          #B     = ATMA + alpha*identity(len(ATMA))
          #c     = ATDb
          #ATA   = real(ifft2(conj(ahat) * real(ifft2(ahat))))
          #prec  = ATA + alpha*identity(len(ATMA))
          #nx,ny = shape(c)
          #x0    = zeros(nx*ny)
          #c     = reshape(c, nx*ny, order='F')
          #x_filt, hist = cg(B, c, x0=x0, tol=1e-4, maxiter=250)
          # Landweber iteration :
          nx,ny = shape(ATDb)
          x     = zeros(shape(ahat))
          i     = 0
          while i < 250:
            i    += 1
            dftx  = fft2(x)
            MAx   = M * real(ifft2(ahat * dftx))
            ATMAx = real(ifft2(conj(ahat) * fft2(MAx)))
            x     = x - tau * (ATMAx - ATDb)
            t     = norm(ATMAx - ATDb)**2 >= (nx * ny)**2 * sig
            print norm(ATMAx - ATDb)**2
          l = nx/4
          r = nx*(1 - 1/4.0)
          t = ny/4
          b = ny*(1 - 1/4.0)
          x_filt = x[l:r, t:b]
        else:
          B  = self.B
          c  = self.c
          M  = self.M
          x0 = zeros(len(B))
          x_filt, hist = cg(B, c, x0=x0, tol=1e-4, maxiter=250, M=M)
    return x_filt
  
  def get_ralpha(self, alpha, xalpha):
    """
    get r-alpha for L-curve.
    """
    b  = self.b
    if not self.per_BC:
      A1 = self.A1
      A2 = self.A2
      ralpha = dot(dot(A1, xalpha - b), A2.T)
    else:
      ahat   = self.ahat
      ralpha = real(ifft2(ahat*fft2(xalpha - b)))
    return ralpha

  def plot_filt(self, ax, x_filt, alpha, tit, tau=False):
    """
    plot the filtered solution.
    """
    im      = ax.imshow(x_filt, cmap=self.cmap)
    divider = make_axes_locatable(ax)
    cax     = divider.append_axes("right", size="5%", pad=0.05)
    if tau:
      st = r'Landweber Filtered, $\tau = %.2f$'
      ax.set_title(st % self.tau)
    else:
      st = tit + r' Filtered, $\alpha = %.2E$'
      ax.set_title(st % alpha)
    ax.axis('off')
    colorbar(im, cax=cax)
  
  def plot_true(self, ax):
    """
    plot the true and blurred solution.
    """
    x_true  = self.x_true
    im      = ax.imshow(x_true, cmap=self.cmap)
    divider = make_axes_locatable(ax)
    cax     = divider.append_axes("right", size="5%", pad=0.05)
    ax.set_title(r'$\vec{x}_{true}$')
    ax.axis('off')
    colorbar(im, cax=cax)
  
  def plot_b(self, ax):
    """
    plot the true and blurred solution.
    """
    b       = self.b
    im      = ax.imshow(b, cmap=self.cmap)
    divider = make_axes_locatable(ax)
    cax     = divider.append_axes("right", size="5%", pad=0.05)
    ax.set_title(r'$\vec{b}$')
    ax.axis('off')
    colorbar(im, cax=cax)
  
  def plot_U_vectors(self, ax):
    """
    plot the first 8 orthogonal U vectors.
    """
    U = self.U
    t = self.t
    fig = figure(figsize=(12,7))
    axs = []
    for i in range(8):
      ax = fig.add_subplot(240 + (i+1))
      ax.plot(t, U[:,i], 'k-', lw=2.0)
      ax.grid()
      if i > 3: ax.set_xlabel(r'$t$')
      ax.set_title(r'$\vec{u}_{%i}$' % i)
    show()

  def plot_UTb_vectors(self, ax):
    """
    plot the singular vectors UTb on a log y-axis.
    """
    U  = self.U
    S  = self.S
    b  = self.b
    Ax = self.Ax
    t  = self.t

    ax.semilogy(t, S, 'r', lw=2, label=r'$\Sigma$')
    ax.semilogy(t, abs(dot(U.T, b)),    'ws', lw=2,
                label=r'$\vec{u}_i^T \cdot \vec{b}$')
    ax.semilogy(t, abs(dot(U.T, b)/S),  'w^', lw=2, 
                label=r'$\frac{\vec{u}_i^T \cdot \vec{b}}{\sigma}$')
    ax.semilogy(t, abs(dot(U.T, Ax)),   'ks', lw=2, 
                label=r'$\vec{u}_i^T \cdot A\vec{x}$')
    ax.semilogy(t, abs(dot(U.T, Ax)/S), 'k^', lw=2, 
                label=r'$\frac{\vec{u}_i^T \cdot A\vec{x}}{\sigma}$')
    ax.set_xlabel(r'$t$')
    leg = ax.legend(loc='upper left')
    leg.get_frame().set_alpha(0.5)
    ax.grid()

  def plot_VTx_variance(self, ax):
    """
    plot the variance values in V^T x_LS.
    """
    V       = self.V
    A       = self.A
    b       = self.b
    Ax      = self.Ax
    x_ls_no = solve(A,b)
    x_ls    = solve(A,Ax)

    ax.plot(dot(V.T, x_ls),    'r-',  label='clean', lw=2.0)
    ax.plot(dot(V.T, x_ls_no), 'ko-', label='noisy')
    ax.set_xlabel(r'$i$')
    ax.set_title(r'$\vec{v}_i^T \vec{x}_{LS}$')
    ax.grid()
    leg = ax.legend(loc='upper center')
    leg.get_frame().set_alpha(0.5)

  def plot_variance(self, ax):
    """
    plot the variance values sigma^2 / sigma_i^2.
    """
    sigma = self.sigma
    S     = self.S

    ax.plot(sigma/S**2, 'ko-',  label='variance', lw=2.0)
    ax.set_yscale('log')
    ax.set_title(r'Variance $\sigma^2/\sigma_i^2$')
    ax.set_xlabel(r'$i$')
    ax.grid()



