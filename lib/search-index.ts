import { benchmarkDataService, Probe, AttackFamilyMeta, ScenarioMeta, KNOWN_AGENTS } from './data-service'

export interface SearchResultItem {
  id: string
  type: 'probe' | 'family' | 'scenario' | 'model' | 'report'
  title: string
  subtitle: string
  badgeText: string
  link: string
}

export function searchBenchmark(query: string): SearchResultItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return []

  const results: SearchResultItem[] = []

  // 1. Search Probes
  const probes: Probe[] = benchmarkDataService.getAllProbes()
  probes.forEach(probe => {
    if (
      probe.id.toLowerCase().includes(q) ||
      probe.title.toLowerCase().includes(q) ||
      probe.attack_family.toLowerCase().includes(q) ||
      probe.attack_variant.toLowerCase().includes(q) ||
      probe.scenario.toLowerCase().includes(q) ||
      (probe.tags && probe.tags.some(t => t.toLowerCase().includes(q)))
    ) {
      results.push({
        id: probe.id,
        type: 'probe',
        title: `${probe.id}: ${probe.title}`,
        subtitle: `Family: ${probe.attack_family} | Difficulty: ${probe.difficulty} | Layer: ${(probe.affected_layers || []).join(', ')}`,
        badgeText: 'Probe',
        link: `/corpus/probes/${probe.id}`,
      })
    }
  })

  // 2. Search Attack Families
  const families: AttackFamilyMeta[] = benchmarkDataService.getAttackFamilies()
  families.forEach(fam => {
    if (
      fam.id.toLowerCase().includes(q) ||
      fam.name.toLowerCase().includes(q) ||
      fam.description.toLowerCase().includes(q)
    ) {
      results.push({
        id: fam.id,
        type: 'family',
        title: fam.name,
        subtitle: `${fam.probeCount} Probes | Threat Model: ${fam.threatModel}`,
        badgeText: 'Attack Family',
        link: `/corpus/families/${fam.id}`,
      })
    }
  })

  // 3. Search Scenarios
  const scenarios: ScenarioMeta[] = benchmarkDataService.getScenarios()
  scenarios.forEach(scen => {
    if (
      scen.id.toLowerCase().includes(q) ||
      scen.name.toLowerCase().includes(q) ||
      scen.description.toLowerCase().includes(q)
    ) {
      results.push({
        id: scen.id,
        type: 'scenario',
        title: scen.name,
        subtitle: `${scen.description} (Risk: ${scen.riskLevel})`,
        badgeText: 'Scenario',
        link: `/corpus?scenario=${scen.id}`,
      })
    }
  })

  // 4. Search Models & Leaderboards
  KNOWN_AGENTS.forEach(m => {
    if (m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)) {
      results.push({
        id: m.id,
        type: 'model',
        title: m.name,
        subtitle: `Agent ID: ${m.id} | ${m.badge}`,
        badgeText: 'Model',
        link: `/models`,
      })
    }
  })

  return results.slice(0, 15) // Limit to top 15 results
}
