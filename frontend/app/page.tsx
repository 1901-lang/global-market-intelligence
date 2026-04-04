import { Navbar } from './components/layout/Navbar'
import { Footer } from './components/layout/Footer'
import { HeroSection } from './components/landing/HeroSection'
import { DashboardMockup } from './components/landing/DashboardMockup'
import { InfrastructureStrip } from './components/landing/InfrastructureStrip'
import { ProblemSolutionSection } from './components/landing/ProblemSolutionSection'
import { GlobalMarketStateSection } from './components/landing/GlobalMarketStateSection'
import { CapabilitiesSection } from './components/landing/CapabilitiesSection'
import { MethodologySection } from './components/landing/MethodologySection'
import { ExplainabilitySection } from './components/landing/ExplainabilitySection'
import { TargetUsersSection } from './components/landing/TargetUsersSection'
import { FinalCTASection } from './components/landing/FinalCTASection'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <Navbar />
      <main>
        <HeroSection />
        <DashboardMockup />
        <InfrastructureStrip />
        <ProblemSolutionSection />
        <GlobalMarketStateSection />
        <CapabilitiesSection />
        <MethodologySection />
        <ExplainabilitySection />
        <TargetUsersSection />
        <FinalCTASection />
      </main>
      <Footer />
    </div>
  )
}
