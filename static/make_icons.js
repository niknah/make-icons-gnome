

(() => {
  const spinner = document.getElementById('spinner');
  const errorElem = document.getElementById('error');
  function setup_form(formElement, done) {
    // 1. Grab the form element
  //  const formElement = document.querySelector('#myForm');

    const skip = formElement.querySelector('.skip-button');
    if(skip) {
      skip.addEventListener('click', () => {
        formElement.classList.add('form-hidden');
        done();
      });
    }

    // 2. Listen for the submit event
    formElement.addEventListener('submit', async (event) => {
      // Prevent the default browser page reload
      event.preventDefault();

      formElement.classList.add('form-hidden');

      // 3. Automatically gather form data and convert to URL-encoded format
      const formData = new FormData(formElement);
      const dataString = new URLSearchParams(formData).toString();
      spinner.classList.remove('form-hidden');

      try {
        // 4. Send the POST request
        const response = await fetch(formElement.action, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          body: dataString // e.g., "username=john&email=john%40example.com"
        });
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        spinner.classList.add('form-hidden');

        console.log('Success:', result);
        return done(result);
        
      } catch (error) {
        console.error('Error submitting form:', error);
        errorElem.innerHTML += error+'<p />';
      	formElement.classList.add('form-hidden');
        spinner.classList.add('form-hidden');
      }
    });


  }

  window.addEventListener('load',() => {
    const makeIconsForm = document.getElementById('make-icons-form');
    const runComfyForm = document.getElementById('run-comfy-form');
    const postprocess = document.getElementById('postprocess');

    setup_form(makeIconsForm, (result) => {
      if(postprocess.value) {
        // ok, we are done     
        const done = document.getElementById('done-message');
        done.classList.remove('form-hidden');
        makeIconsForm.classList.add('postprocess-form');
        makeIconsForm.classList.remove('form-hidden');
        const symlink_needed = document.getElementById('symlink_needed');
        if(result.symlink_needed) {
          symlink_needed.classList.remove('form-hidden');
        }
      } else {
        runComfyForm.classList.remove('form-hidden');
      }
    });

    setup_form(runComfyForm, () => {
      const container = document.getElementById('comfy_container');
      container.classList.remove('form-hidden');

      spinner.classList.remove('form-hidden');
      check_comfy(() => {
        spinner.classList.add('form-hidden');
        postprocess.value=1;
        document.body.classList.add('postprocess');
        makeIconsForm.classList.remove('form-hidden');
      });
    });

  });
})();
