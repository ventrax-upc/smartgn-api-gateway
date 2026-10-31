const REASONS = {
  400: 'Bad Request',
  401: 'Unauthorized',
  403: 'Forbidden',
  404: 'Not Found',
  429: 'Too Many Requests',
  500: 'Internal Server Error',
  502: 'Bad Gateway',
  503: 'Service Unavailable',
  504: 'Gateway Timeout',
};

export function sendError(req, res, status, message) {
  if (res.headersSent) return;
  res.status(status).json({
    status,
    error: REASONS[status] ?? 'Error',
    message,
    correlationId: req.id,
  });
}

export function notFoundHandler(req, res) {
  sendError(req, res, 404, 'Resource not found');
}

// eslint-disable-next-line no-unused-vars
export function errorHandler(err, req, res, _next) {
  // Never leak internals: log server side without secrets, answer generic.
  console.error(`[${req.id}] unhandled error: ${err.message}`);
  sendError(req, res, 500, 'Unexpected error');
}
