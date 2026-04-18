import SwiftUI

/// Instrument-style panel: lifted charcoal surface, optional HUD kicker.
struct CockpitPanel<Content: View>: View {
    var kicker: String?
    var title: String?
    @ViewBuilder var content: () -> Content

    init(kicker: String? = nil, title: String? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.kicker = kicker
        self.title = title
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let kicker, !kicker.isEmpty {
                Text(kicker)
                    .cockpitKickerStyle()
            }
            if let title, !title.isEmpty {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(CockpitTheme.mist)
            }
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(CockpitTheme.charcoal950)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(CockpitTheme.divider, lineWidth: 1)
        )
    }
}
