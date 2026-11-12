window.addEventListener('load', () => {
  window.ui = SwaggerUIBundle({
    url: '../v3/api-docs',
    dom_id: '#swagger-ui',
    deepLinking: true,
    docExpansion: 'list',
    defaultModelsExpandDepth: 0,
    displayRequestDuration: true,
    persistAuthorization:false
  });
});
