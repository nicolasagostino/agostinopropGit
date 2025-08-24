// Get the modal
var modal = document.getElementById("modal");

// Get the image and insert it inside the modal - use its "alt" text as a caption
var modalImg = document.getElementById("modal-image");
var captionText = document.getElementById("caption");

var images = document.getElementsByClassName("gallery-image");
var currentIndex = 0;

function openModal(index) {
    modal.style.display = "block";
    modalImg.src = images[index].src;
    captionText.innerHTML = images[index].alt;
    currentIndex = index;
}

for (let i = 0; i < images.length; i++) {
    images[i].onclick = function () {
        openModal(i);
    }
}

// Get the <span> element that closes the modal
var span = document.getElementsByClassName("close")[0];

// When the user clicks on <span> (x), close the modal
span.onclick = function () {
    modal.style.display = "none";
}

function changeImage(n) {
    currentIndex += n;

    if (currentIndex >= images.length) {
        currentIndex = 0;
    } else if (currentIndex < 0) {
        currentIndex = images.length - 1;
    }

    modalImg.src = images[currentIndex].src;
    captionText.innerHTML = images[currentIndex].alt;
}

// Zoom functionality
modalImg.onclick = function () {
    if (modalImg.classList.contains("zoomed")) {
        modalImg.classList.remove("zoomed");
    } else {
        modalImg.classList.add("zoomed");
    }
}