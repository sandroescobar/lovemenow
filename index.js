
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
}


sign_in_button = document.querySelector("#signInButton");
console.log("button found:" , sign_in_button);

sign_in_button.addEventListener("click", function(){
    modal =  document.querySelector(".modal-overlay");
    console.log("modal found:" , modal);
    modal.classList.add('active');
});

// everything above is to open the modal to sign in

function closeModal() {
  document.querySelector('#loginModal').classList.remove('active');
  document.querySelector('#registerModal').classList.remove('active');
}
//everything above is to close the login_modal


/* ───────── Password show / hide for every eye button ───────── */
/* ─── index.js ─── */



// no DOMContentLoaded wrapper needed when script is at end-of-body
const pwd = document.getElementById('loginPassword');
const eye = document.getElementById('eyeButton');

if (pwd && eye) {
  eye.addEventListener('click', () => {
    const hidden = pwd.type === 'password';
    pwd.type    = hidden ? 'text' : 'password';
    eye.classList.toggle('fa-eye',       hidden);
    eye.classList.toggle('fa-eye-slash', !hidden);
  });
}

// — your existing login snippet lives here —
// const pwd = document.getElementById('loginPassword');
// const eye = document.getElementById('eyeButton');
// if (pwd && eye) { … }

// ─── ADD THIS AT THE BOTTOM OF index.js ───
document.querySelectorAll('.password-toggle').forEach(icon => {
  // the <input> is the immediately preceding sibling
  const input = icon.previousElementSibling;
  if (!input) return;

  icon.addEventListener('click', () => {
    // 1) flip the field mask
    const hidden = input.type === 'password';
    input.type   = hidden ? 'text' : 'password';

    // 2) swap the two Font-Awesome classes
    icon.classList.toggle('fa-eye',       hidden);
    icon.classList.toggle('fa-eye-slash', !hidden);
  });
});









