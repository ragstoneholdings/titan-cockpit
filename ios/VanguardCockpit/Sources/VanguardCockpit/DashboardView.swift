import Charts
import SwiftUI

private let sovereigntyTargetPercent: Double = 80

struct DashboardView: View {
    var cockpit: CockpitResponseDTO?
    var ragstoneLine: String
    var qboLine: String
    var reconDay: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Flight deck")
                .cockpitKickerStyle()
            primaryBand
            if let s = cockpit?.sovereignty {
                Text("Sovereignty")
                    .cockpitKickerStyle()
                Text(s.sovereignty_line.isEmpty ? "—" : s.sovereignty_line)
                    .font(.headline)
                    .foregroundStyle(CockpitTheme.mist)
                sovereigntyChart(blended: s.sovereignty_quotient_blended_percent, base: s.sovereignty_quotient_percent)
                Text("Target strategic bandwidth ≥ \(Int(sovereigntyTargetPercent))% (blended SQ vs. threshold)")
                    .cockpitBodySecondary()
                if let ex = cockpit?.vanguard_executed {
                    Text("Execution mix")
                        .cockpitKickerStyle()
                        .padding(.top, 4)
                    executionMixChart(ex)
                }
                Text("Authority: \(s.operational_authority_line)")
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
                Text("Finance: \(s.financial_sovereignty_line)")
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
                Text("Physical: \(s.physical_baseline_line)")
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
            } else {
                Text("Refresh for sovereignty data.")
                    .cockpitBodySecondary()
            }
            NavigationLink {
                PowerTrioView(reconDay: reconDay)
            } label: {
                HStack {
                    Text("Power Trio")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(CockpitTheme.mist)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(CockpitTheme.mistMuted)
                }
                .padding(12)
                .background(CockpitTheme.charcoal950)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(CockpitTheme.divider, lineWidth: 1)
                )
            }
            .buttonStyle(.plain)

            if !ragstoneLine.isEmpty {
                Text(ragstoneLine)
                    .font(.caption)
                    .foregroundStyle(CockpitTheme.mistMuted)
            }
            if !qboLine.isEmpty {
                Text("QBO: \(qboLine)")
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
            }
            if let sig = cockpit?.schedule_day_signals, !sig.summary_line.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                Text(sig.summary_line)
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
            }
            if let sentry = cockpit?.integrity_sentry_state, sentry != "NOMINAL" {
                Text("Integrity: \(sentry)")
                    .font(.caption)
                    .foregroundStyle(sentry == "CRITICAL" ? Color.red : CockpitTheme.industrialAmber)
            }
            if let bugs = cockpit?.dead_bug_alerts, !bugs.isEmpty {
                Text(bugs.map { b in
                    let hint = b.title_hint.isEmpty ? b.project_name : b.title_hint
                    return hint.isEmpty ? b.project_name : hint
                }.joined(separator: " · "))
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
            }
            if let c = cockpit, c.executive_score_percent > 0 {
                Text("Executive score \(String(format: "%.0f", c.executive_score_percent))%")
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
                    .monospacedDigit()
            }
            if let signals = cockpit?.firefighting_signals, !signals.isEmpty {
                Text(signals.joined(separator: " · "))
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
            }
            flagsRow
        }
    }

    @ViewBuilder
    private var primaryBand: some View {
        if let sum = cockpit?.execution_day_summary, !sum.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            Text(sum)
                .font(.subheadline)
                .foregroundStyle(CockpitTheme.mist)
        }
        if let rw = cockpit?.runway {
            let line = Self.runwayOneLine(rw)
            if !line.isEmpty {
                Text(line)
                    .cockpitBodySecondary()
            }
        }
        if let c = cockpit, c.todoist_inbox_open_count > 0 || !c.inbox_slaughter_gate_ok {
            Text("Inbox open: \(c.todoist_inbox_open_count) · gate \(c.inbox_slaughter_gate_ok ? "clear" : "blocked")")
                .font(.caption)
                .foregroundStyle(c.inbox_slaughter_gate_ok ? CockpitTheme.mistMuted : CockpitTheme.industrialAmber)
                .monospacedDigit()
        }
    }

    private static func runwayOneLine(_ r: RunwayPayloadDTO) -> String {
        if r.runway_conflict {
            let hint = r.conflict_summary ?? ""
            return hint.isEmpty ? "Runway conflict" : "Runway: \(hint.prefix(160))"
        }
        if !r.notification_markdown.isEmpty {
            return String(r.notification_markdown.prefix(200))
        }
        if r.prep_gap_minutes > 0 {
            return "Prep gap \(r.prep_gap_minutes)m"
        }
        return ""
    }

    @ViewBuilder
    private func sovereigntyChart(blended: Double, base: Double) -> some View {
        Chart {
            BarMark(
                x: .value("Metric", "Blended"),
                y: .value("%", min(100, max(0, blended)))
            )
            .foregroundStyle(CockpitTheme.chartSeriesPrimary)
            BarMark(
                x: .value("Metric", "Deep share"),
                y: .value("%", min(100, max(0, base)))
            )
            .foregroundStyle(CockpitTheme.chartSeriesSecondary)
            RuleMark(y: .value("Target", sovereigntyTargetPercent))
                .foregroundStyle(CockpitTheme.industrialAmber.opacity(0.85))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
        }
        .chartYScale(domain: 0 ... 100)
        .frame(height: 140)
    }

    @ViewBuilder
    private func executionMixChart(_ ex: VanguardExecutedDTO) -> some View {
        let total = max(1, ex.deep + ex.mixed + ex.shallow)
        Chart {
            BarMark(x: .value("Kind", "Deep"), y: .value("n", ex.deep))
                .foregroundStyle(CockpitTheme.chartDeep)
            BarMark(x: .value("Kind", "Mixed"), y: .value("n", ex.mixed))
                .foregroundStyle(CockpitTheme.chartMixed)
            BarMark(x: .value("Kind", "Shallow"), y: .value("n", ex.shallow))
                .foregroundStyle(CockpitTheme.chartShallow)
        }
        .frame(height: 100)
        .chartYScale(domain: 0 ... Double(max(total, 3)))
    }

    @ViewBuilder
    private var flagsRow: some View {
        if let c = cockpit {
            Text("Annunciators")
                .cockpitKickerStyle()
            HStack(spacing: 8) {
                flagChip("Air gap", c.air_gap_active)
                flagChip("Midday", c.midday_shield_active)
                flagChip("Identity", c.identity_alignment_window_active)
                flagChip("Inbox OK", c.inbox_slaughter_gate_ok)
            }
            .font(.caption2)
            if !c.firewall_audit_summary.isEmpty {
                Text(c.firewall_audit_summary)
                    .font(.caption2)
                    .foregroundStyle(CockpitTheme.mistMuted)
            }
        }
    }

    private func flagChip(_ title: String, _ on: Bool) -> some View {
        Text(title + (on ? " · on" : ""))
            .font(.caption2.weight(on ? .semibold : .regular))
            .foregroundStyle(on ? CockpitTheme.mist : CockpitTheme.mistMuted)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(on ? CockpitTheme.annunciatorOnFill : CockpitTheme.annunciatorOffFill)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(on ? CockpitTheme.annunciatorOnBorder : CockpitTheme.annunciatorOffBorder, lineWidth: 1)
            )
    }
}
