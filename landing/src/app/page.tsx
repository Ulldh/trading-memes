import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import { Ticker } from "@/components/Ticker";
import Pipeline from "@/components/Pipeline";
import Stats from "@/components/Stats";
import Backtesting from "@/components/Backtesting";
import SocialProof from "@/components/SocialProof";
import Pricing from "@/components/Pricing";
import FAQ from "@/components/FAQ";
import FinalCTA from "@/components/FinalCTA";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <main id="main-content" className="min-h-screen bg-dark-900">
      {/* Header fijo: Navbar + Ticker (siempre visibles) */}
      <header className="fixed top-0 left-0 right-0 z-50">
        <Navbar />
        <Ticker />
      </header>

      {/* Contenido con padding para compensar header fijo */}
      <div className="pt-[88px]">
        <Hero />
        <div id="pipeline"><Pipeline /></div>
        <div id="stats"><Stats /></div>
        <div id="backtesting"><Backtesting /></div>
        <SocialProof />
        <div id="pricing"><Pricing /></div>
        <div id="faq"><FAQ /></div>
        <FinalCTA />
        <Footer />
      </div>
    </main>
  );
}
