// ============================================================
// JAVASCRIPT — DASHBOARD LOGISTIQUE
// ============================================================

// Horloge dynamique
function updateClock() {
    const clock = document.getElementById("live-clock");

    if (clock) {
        const now = new Date();

        const formatted = now.toLocaleString("fr-FR", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });

        clock.innerHTML = formatted;
    }
}

setInterval(updateClock, 1000);
updateClock();


// Effet visuel sur les cartes KPI
function animateCards() {
    const cards = document.querySelectorAll(".kpi-card");

    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.08}s`;
    });
}

setTimeout(animateCards, 500);


// Message console pour démonstration
console.log("🚚 Logistics Control Tower loaded successfully");
console.log("Kafka → PostGIS → Streamlit dashboard");