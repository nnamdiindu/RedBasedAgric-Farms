// Hero background image carousel
document.addEventListener("DOMContentLoaded", function () {
    const slides = document.querySelectorAll(".hero-bg-slide");
    const ourFarmLink = document.querySelector('a[href="#hero-background-slider"]');

    let currentSlide = 0;
    let slideInterval;

    function showSlide(index) {
        slides.forEach(slide => slide.classList.remove("active"));

        currentSlide = index;
        slides[currentSlide].classList.add("active");
    }

    function startSlider() {
        if (slides.length > 1) {
            slideInterval = setInterval(() => {
                showSlide((currentSlide + 1) % slides.length);
            }, 5000);
        }
    }

    if (slides.length > 0) {
        showSlide(0);
        startSlider();
    }

    if (ourFarmLink) {
        ourFarmLink.addEventListener("click", function () {
            if (slides.length > 0) {
                clearInterval(slideInterval);
                showSlide(0);
                startSlider();
            }
        });
    }
});


// Best Sellers carousel: arrow-driven scroll with synced dot pagination.
(function () {
    const track = document.getElementById('bsTrack');
    const prevBtn = document.getElementById('bsPrev');
    const nextBtn = document.getElementById('bsNext');
    const dotsWrap = document.getElementById('bsDots');
    if (!track) return;

    const cards = Array.from(track.children);

    function cardsPerView() {
        return window.innerWidth < 768 ? 1 : 2;
    }

    function pageCount() {
        return Math.max(1, Math.ceil(cards.length / cardsPerView()));
    }

    function buildDots() {
        dotsWrap.innerHTML = '';
        const pages = pageCount();
        for (let i = 0; i < pages; i++) {
            const dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'bs-dot';
            dot.setAttribute('aria-label', 'Go to slide ' + (i + 1));
            dot.addEventListener('click', () => scrollToPage(i));
            dotsWrap.appendChild(dot);
        }
        updateDots();
    }

    function currentPage() {
        const perView = cardsPerView();
        const cardWidth = cards[0].getBoundingClientRect().width + 20; // + gap
        const index = Math.round(track.scrollLeft / (cardWidth * perView));
        return Math.min(index, pageCount() - 1);
    }

    function updateDots() {
        const dots = Array.from(dotsWrap.children);
        const active = currentPage();
        dots.forEach((d, i) => d.classList.toggle('is-active', i === active));
    }

    function scrollToPage(page) {
        const perView = cardsPerView();
        const cardWidth = cards[0].getBoundingClientRect().width + 20;
        track.scrollTo({ left: page * cardWidth * perView, behavior: 'smooth' });
    }

    function scrollByCards(direction) {
        const cardWidth = cards[0].getBoundingClientRect().width + 20;
        track.scrollBy({ left: direction * cardWidth * cardsPerView(), behavior: 'smooth' });
    }

    prevBtn.addEventListener('click', () => scrollByCards(-1));
    nextBtn.addEventListener('click', () => scrollByCards(1));

    let scrollTimeout;
    track.addEventListener('scroll', () => {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(updateDots, 80);
    });

    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(buildDots, 150);
    });

    buildDots();
})();