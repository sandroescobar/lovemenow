


function switchModal(which) {
  // 1) Grab references to the two modal elements:
  const login_modal    = document.querySelector("#loginModal");
  const register_modal = document.querySelector("#registerModal");

  // 2) First, remove 'active' from both, so you start clean
  login_modal.classList.remove('active');
  register_modal.classList.remove('active');

  // 3) Now decide which one to SHOW
  if (which === 'register') {
    // Show the register modal
    register_modal.classList.add('active');
  }
  else if (which === 'login') {
    // Show the login modal
    login_modal.classList.add('active');
  }

  // 4) Reinitialize password toggles when switching modals
  setTimeout(reinitializePasswordToggles, 100);
}


sign_in_button = document.querySelector("#signInButton");
console.log("button found:" , sign_in_button);

sign_in_button.addEventListener("click", function(){
    modal =  document.querySelector(".modal-overlay");
    console.log("modal found:" , modal);
    modal.classList.add('active');
    // Reinitialize password toggles when modal opens
    setTimeout(reinitializePasswordToggles, 100);
});

// everything above is to open the modal to sign in

function closeModal() {
  document.querySelector('#loginModal').classList.remove('active');
  document.querySelector('#registerModal').classList.remove('active');
}
//everything above is to close the login_modal


/* ───────── Password show / hide for ALL password fields ───────── */

// Track which icons already have event listeners to prevent duplicates
const togglesInitialized = new Set();

function initializePasswordToggles() {
  // Handle all password toggle icons with .password-toggle class
  const allToggleIcons = document.querySelectorAll('.password-toggle');

  allToggleIcons.forEach(icon => {
    // Skip if already initialized
    if (togglesInitialized.has(icon)) return;

    // Find the associated password input (previous sibling)
    const passwordInput = icon.previousElementSibling;

    if (!passwordInput) return;

    // Set initial state: password hidden, eye closed
    passwordInput.type = 'password';
    icon.classList.remove('fa-eye');
    icon.classList.add('fa-eye-slash');

    // Add click event listener (only once)
    const toggleHandler = () => {
      const isPasswordHidden = passwordInput.type === 'password';

      if (isPasswordHidden) {
        // Show password: change to text, show open eye
        passwordInput.type = 'text';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
      } else {
        // Hide password: change to password, show closed eye
        passwordInput.type = 'password';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
      }
    };

    icon.addEventListener('click', toggleHandler);

    // Mark as initialized
    togglesInitialized.add(icon);
  });
}


// Re-initialize when modals are opened (in case DOM changes)
function reinitializePasswordToggles() {
  initializePasswordToggles();
}

initializePasswordToggles();


document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".toast").forEach((toast, i) => {
    const ttl = 5000 + i * 100;           // 5 s + small stagger
    setTimeout(() => {
      toast.style.animation = "slideOut .4s forwards";
      toast.addEventListener("animationend", () => toast.remove());
    }, ttl);
  });
});



var close_login_modal = document.querySelector('.modal-close');

close_login_modal.addEventListener('click', function() {
    logged_in_modal = document.querySelector('#loggedModal')
    logged_in_modal.classList.remove('active')
});






