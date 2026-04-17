document.addEventListener('DOMContentLoaded', () => {
    const createDot = () => {
        const dot = document.createElement('div');
        dot.className = 'moving-dot';
        document.querySelector('.curve-container').appendChild(dot);
        
        dot.addEventListener('animationend', () => {
            dot.remove();
        });
    };

    setInterval(createDot, 2000);
    createDot();
});
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
    });
});

document.querySelectorAll('.button').forEach(button => {
    button.addEventListener('mouseenter', () => {
        button.style.transform = 'translateY(-2px)';
    });
    button.addEventListener('mouseleave', () => {
        button.style.transform = 'translateY(0)';
    });
});
document.querySelectorAll('.footer a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

const exploreBtn = document.querySelector('.explore-btn');
if (exploreBtn) {
    exploreBtn.addEventListener('mouseenter', () => {
        exploreBtn.style.transform = 'translateX(5px)';
    });
    exploreBtn.addEventListener('mouseleave', () => {
        exploreBtn.style.transform = 'translateX(0)';
    });
}