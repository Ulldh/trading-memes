import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Ticker from "@/components/Ticker";
import Pipeline from "@/components/Pipeline";
import Stats from "@/components/Stats";
import Backtesting from "@/components/Backtesting";
import Pricing from "@/components/Pricing";
import FAQ from "@/components/FAQ";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-dark-900">
      {/* Navbar fija + Ticker debajo */}
      <Navbar />
      <div className="pt-14">
        <Ticker />
      </div>

      {/* Secciones con IDs para navegacion */}
      <Hero />
      <div id="pipeline"><Pipeline /></div>
      <div id="stats"><Stats /></div>
      <div id="backtesting"><Backtesting /></div>
      <div id="pricing"><Pricing /></div>
      <div id="faq"><FAQ /></div>
      <Footer />
    </main>
  );
}
