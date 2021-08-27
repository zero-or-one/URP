import numpy as np

def parameter_count(model):
    count=0
    for p in model.parameters():
        count+=np.prod(np.array(list(p.shape)))
    print(f'Total Number of Parameters: {count}')

def vectorize_params(model):
    param = []
    for p in model.parameters():
        param.append(p.data.view(-1).cpu().numpy())
    return np.concatenate(param)

def print_param_shape(model):
    for k,p in model.named_parameters():
        print(k,p.shape)

def get_pdf(weights):
    pass

'''!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'''
### Change it, place into forgetting later
def lin_exact(X, Y, reg=1e-4):
    """
    Exact retraining using normal form of the parameters.
    Solves min sum[((theta^T x_i - y_i)^2)/2] + reg * (||theta||^2)/2
    Normal form: (X^T X + reg * I)theta = X^T Y.
    Args:
        X: (n x d matrix) Covariate matrix
        Y: (n x 1 vector) Response vector
        reg: (float) Per-data point regularization parameter
    Returns:
        theta: (d x 1 vector) Fitted coefficients
    """
    n = len(Y)
    d = len(X[0, :])
    theta = np.linalg.solve(np.matmul(X.T, X) + reg * np.eye(d), np.matmul(X.T, Y))
    return theta

def lin_inf(X, Y, theta, ind, invhess=None, reg=1e-4):
    """
    Approximate retraining via infuence method
    Args:
        X: (n x d matrix) Covariate matrix
        Y: (n x 1 vector) Response vector
        theta: (d x 1 vector) Current value of parameters to be updated
        ind: (k x 1 list) List of indices to be removed
        invhess: (d x d matrix, optional) Pre-computed inverse Hessian
        reg: (float) Fixed regularization strength
    Returns:
        updated: (d x 1 vector) Updated parameters
    """
    n = len(Y)
    k = len(ind)
    d = len(theta)

    # Note: We don't need to add the regularization term to the gradient because
    # we want grad[L_{\k}(theta_full)].
    grad = np.zeros(d)
    for i in ind:
        grad += (np.dot(X[i, :], theta) - Y[i]) * X[i, :]

    if invhess is not None:
        updated = theta + np.matmul(invhess, grad)
    else:
        updated = theta + np.linalg.solve(np.matmul(X.T, X) + reg * np.eye(d), grad)
    return updated

def lin_res(X, Y, theta, ind, H=None, reg=1e-4):
    """
    Approximate retraining via the projective residual update.
    Args:
        X: (n x d matrix) Covariate matrix
        Y: (n x 1 vector) Response vector
        theta: (d x 1 vector) Current value of parameters to be updated
        ind: (k x 1 list) List of indices to be removed
        H: (n x n matrix, optional) Hat matrix X (X^T X)^{-1} X^T
    Returns:
        updated: (d x 1 vector) Updated parameters
    """
    d = len(X[0])
    k = len(ind)

    # Step 1: Compute LKO predictions
    LKO = LKO_pred(X, Y, ind, H, reg)

    # Step 2: Eigendecompose B
    # 2.I
    U, C = gram_schmidt(X[ind, :])
    # 2.II
    Cmatrix = np.matmul(C.T, C)
    eigenval, a = np.linalg.eigh(Cmatrix)
    V = np.matmul(a.T, U)

    # Step 3: Perform the update
    # 3.I
    grad = np.zeros(d)
    for i in range(k):
        grad += (np.dot(X[ind[i], :], theta) - LKO[i]) * X[ind[i], :]
    # 3.II
    step = np.zeros(d)
    for i in range(k):
        factor = 1 / eigenval[i] if eigenval[i] > 1e-10 else 0
        step += factor * np.dot(V[i, :], grad) * V[i, :]
    # 3.III
    update = theta - step
    return update

def gram_schmidt(X):
    """
    Uses numpy's qr factorization method to perform Gram-Schmidt.
    Args:
        X: (k x d matrix) X[i] = i-th vector
    Returns:
        U: (k x d matrix) U[i] = i-th orthonormal vector
        C: (k x k matrix) Coefficient matrix, C[i] = coeffs for X[i], X = CU
    """
    (k, d) = X.shape
    if k <= d:
        q, r = np.linalg.qr(np.transpose(X))
    else:
        q, r = np.linalg.qr(np.transpose(X), mode='complete')
    U = np.transpose(q)
    C = np.transpose(r)
    return U, C


def LKO_pred(X, Y, ind, H=None, reg=1e-4):
    """
    Computes the LKO model's prediction values on the left-out points.
    Args:
        X: (n x d matrix) Covariate matrix
        Y: (n x 1 vector) Response vector
        ind: (k x 1 list) List of indices to be removed
        H: (n x n matrix, optional) Hat matrix X (X^T X)^{-1} X^T
    Returns:
        LKO: (k x 1 vector) Retrained model's predictions on X[i], i in ind
    """
    n = len(Y)
    k = len(ind)
    d = len(X[0, :])
    if H is None:
        H = np.matmul(X, np.linalg.solve(np.matmul(X.T, X) + reg * np.eye(d), X.T))

    LOO = np.zeros(k)
    for i in range(k):
        idx = ind[i]
        # This is the LOO residual y_i - \hat{y}^{LOO}_i
        LOO[i] = (Y[idx] - np.matmul(H[idx, :], Y)) / (1 - H[idx, idx])

    # S = I - T from the paper
    S = np.eye(k)
    for i in range(k):
        for j in range(k):
            if j != i:
                idx_i = ind[i]
                idx_j = ind[j]
                S[i, j] = -H[idx_i, idx_j] / (1 - H[idx_i, idx_i])

    LKO = np.linalg.solve(S, LOO)

    return Y[ind] - LKO