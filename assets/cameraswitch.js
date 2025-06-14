function switchCamera() {
// Send a request to the Flask route to switch the camera
  fetch('/switch_camera', { method: 'POST' })
    .then(response => {
      console.log("Camera switched");
      // Refresh the page to load the new video feed
      window.location.reload();
    })
    .catch(error => {
      console.error('Error switching camera:', error);
    });
}