// Mensaje en consola
console.log('Página cargada correctamente');

// Cambiar el texto del botón cuando pasas el mouse
document.querySelector('.boton').addEventListener('mouseover', function() {
    this.textContent = '¡Abrir ahora!';
});

document.querySelector('.boton').addEventListener('mouseout', function() {
    this.textContent = 'Abrir en Telegram';
});