import Image from "next/image";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-white font-sans text-black selection:bg-black selection:text-white dark:bg-zinc-950 dark:text-white dark:selection:bg-white dark:selection:text-black">
      <nav className="flex w-full max-w-7xl items-center justify-between px-6 py-8">
        <div className="text-xl font-bold tracking-tighter">UPSCRÖLLED PULSE</div>
        <div className="hidden space-x-8 text-sm font-medium md:flex">
          <a href="#features" className="hover:text-zinc-500">Features</a>
          <a href="#analytics" className="hover:text-zinc-500">Analytics</a>
          <a href="#pricing" className="hover:text-zinc-500">Pricing</a>
        </div>
        <button className="rounded-full bg-black px-5 py-2 text-sm font-semibold text-white dark:bg-white dark:text-black">
          Get Started
        </button>
      </nav>

      <main className="flex flex-1 flex-col items-center px-6 text-center">
        <section className="mt-20 max-w-4xl py-20">
          <div className="mb-6 inline-flex items-center rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs font-semibold dark:border-zinc-800 dark:bg-zinc-900">
            <span className="mr-2 flex h-2 w-2 rounded-full bg-blue-500 animate-pulse"></span>
            Trending: UpScrolled Hits #1 on App Store
          </div>
          <h1 className="text-5xl font-bold leading-tight tracking-tighter sm:text-7xl">
            The Growth Engine for the <br /> 
            <span className="text-zinc-500">New Era of Social.</span>
          </h1>
          <p className="mt-8 text-lg text-zinc-600 dark:text-zinc-400 sm:text-xl">
            Migrate from TikTok, analyze engagement, and dominate the UpScrolled feed with AI-powered insights.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <button className="h-14 w-full rounded-xl bg-black px-8 text-lg font-bold text-white transition-all hover:scale-105 dark:bg-white dark:text-black sm:w-auto">
              Start Your Migration
            </button>
            <button className="h-14 w-full rounded-xl border border-zinc-200 px-8 text-lg font-bold transition-all hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900 sm:w-auto">
              View Live Trends
            </button>
          </div>
        </section>

        <section id="features" className="w-full max-w-7xl py-32">
          <div className="grid grid-cols-1 gap-12 md:grid-cols-3">
            {[
              {
                title: "One-Click Sync",
                description: "Automatically port your TikTok library to UpScrolled with optimized metadata."
              },
              {
                title: "Pulse Analytics",
                description: "Deep insights into the UpScrolled algorithm to help your content go viral."
              },
              {
                title: "AI Hook Engine",
                description: "Generate high-converting video hooks tailored for the UpScrolled community."
              }
            ].map((feature, i) => (
              <div key={i} className="flex flex-col items-start text-left">
                <div className="mb-4 h-12 w-12 rounded-lg bg-zinc-100 dark:bg-zinc-900"></div>
                <h3 className="text-xl font-bold">{feature.title}</h3>
                <p className="mt-2 text-zinc-600 dark:text-zinc-400">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="w-full border-t border-zinc-100 py-12 px-6 dark:border-zinc-900">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 md:flex-row">
          <div className="text-sm text-zinc-500">
            © 2026 UpScrolled Pulse. Research-driven SaaS.
          </div>
          <div className="flex space-x-6 text-sm text-zinc-500">
            <a href="#" className="hover:text-black dark:hover:text-white">Twitter</a>
            <a href="#" className="hover:text-black dark:hover:text-white">UpScrolled</a>
            <a href="#" className="hover:text-black dark:hover:text-white">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}