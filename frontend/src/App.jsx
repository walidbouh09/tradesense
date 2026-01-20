import React from 'react'

function Hero() {
  return (
    <header className="hero bg-primary text-white py-5">
      <div className="container">
        <div className="d-flex align-items-center justify-content-between">
          <h1 className="display-5">TradeSense</h1>
          <nav>
            <a className="text-white me-3" href="#features">Fonctionnalités</a>
            <a className="text-white" href="#contact">Contact</a>
          </nav>
        </div>
        <p className="lead mt-4">Plateforme Prop Trading moderne — Analyse, backtesting et paiements simulés.</p>
        <div className="mt-4">
          <a href="/" className="btn btn-light btn-lg me-3">Découvrir</a>
          <a href="/" className="btn btn-outline-light btn-lg">Documentation</a>
        </div>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <div>
      <Hero />
      <main className="container my-5">
        <section id="features" className="row align-items-center">
          <div className="col-md-6">
            <h2>Fonctionnalités professionnelles</h2>
            <ul>
              <li>Backtesting et simulation</li>
              <li>Intégration marché marocain</li>
              <li>Simulation paiements & gestion des utilisateurs</li>
            </ul>
          </div>
          <div className="col-md-6">
            <div className="card shadow-sm">
              <div className="card-body">
                <h5 className="card-title">Prête pour démo</h5>
                <p className="card-text">Connectez le backend et affichez les données réelles.</p>
                <a href="#" className="btn btn-primary">Se connecter au backend</a>
              </div>
            </div>
          </div>
        </section>
      </main>
      <footer className="bg-light py-4">
        <div className="container text-center">© TradeSense</div>
      </footer>
    </div>
  )
}
