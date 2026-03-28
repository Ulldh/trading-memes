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
      <Ticker />
      <Hero />
      <Pipeline />
      <Stats />
      <Backtesting />
      <Pricing />
      <FAQ />
      <Footer />
    </main>
  );
}
