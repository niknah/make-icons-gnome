
async function check_comfy(callback) {
  try {
    // 1. Start the network request
    const response = await fetch('/running_comfy');
    // 2. Check if the HTTP status code is successful (200-299)
    if (!response.ok) {
      console.error(`HTTP error! Status: ${response.status}`);
    }
   
    // 3. Parse the stream into a JavaScript object
    const data = await response.json();

    const container = document.getElementById('comfy_container');
    // 4. Use your parsed JSON data
    if(data.running_comfy) {
      container.classList.remove('no_comfy');
    } else {
      container.classList.add('no_comfy');
      return callback();
    }
    // console.log(data);
  } catch (error) {
    // Catch network failures or parsing issues
    console.error('Fetch operation failed:', error);
  }
  setTimeout(() => check_comfy(callback), 60000);
}

//check_comfy();
