import { Icon } from '../components/Icon';
import { BackBar } from '../components/ui';

const SUPPORT_EMAIL = 'Cinehubscustomercare@gmail.com';
const mailto = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('Support Request - Cinehubs')}`;

const FAQ = [
  ['How do I reset my password?', 'Go to Settings > Password & Security to change your password. Forgot it? Use “Forgot Password?” on the sign-in page.'],
  ['Can I download movies for offline viewing?', 'Yes! Use the Download button on any movie you have access to. The file is saved by your browser.'],
  ['How do I update my profile picture?', 'Visit Settings > Personal Information to update your profile photo.'],
  ['How does paying per movie work?', 'On the Basic plan each movie costs ₦200 and stays unlocked for 10 days. Premium unlocks everything for 30 days.'],
];

export function Support() {
  return (
    <div className="page container">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <BackBar title="Customer Support" />
        <div className="panel center">
          <div className="ok-circle" style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--primary)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
            <Icon name="support" size={32} />
          </div>
          <h2>We&apos;re Here to Help!</h2>
          <p className="muted small mt8">Our support team is ready to assist you with any questions or issues.</p>
        </div>
        <div className="menu mt16">
          <a href={mailto} className="menu-item">
            <span className="ic"><Icon name="mail" /></span>
            <span className="tx">Email Us<small>{SUPPORT_EMAIL}</small></span>
          </a>
          <div className="menu-item">
            <span className="ic"><Icon name="clock" /></span>
            <span className="tx">Support Hours<small>24/7 - Always Available</small></span>
          </div>
        </div>
        <div className="section-label">Frequently Asked Questions</div>
        {FAQ.map(([q, a]) => (
          <details key={q} className="faq">
            <summary>{q} <Icon name="chevronDown" /></summary>
            <p>{a}</p>
          </details>
        ))}
        <a href={mailto} className="btn btn-primary block mt24"><Icon name="mail" /> Send Email</a>
      </div>
    </div>
  );
}

function LegalPage({ title, heading, intro, sections, footer }: { title: string; heading: string; intro?: string; sections: [string, string][]; footer: [string, string] }) {
  return (
    <div className="page container" style={{ paddingTop: 24 }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <BackBar title={title} />
        <h2>{heading}</h2>
        <p className="muted xs mt8">Last updated: June 2026</p>
        {intro && <p className="panel small mt16">{intro}</p>}
        <div className="prose">
          {sections.map(([h, body]) => (
            <div key={h}>
              <h3>{h}</h3>
              <p>{body}</p>
            </div>
          ))}
        </div>
        <div className="panel mt24">
          <h3>{footer[0]}</h3>
          <p className="muted small mt8">{footer[1]}</p>
        </div>
      </div>
    </div>
  );
}

export function Privacy() {
  return (
    <LegalPage
      title="Privacy Policy"
      heading="Your Privacy Matters"
      sections={[
        ['Introduction', 'Cinehubs respects your privacy and is committed to protecting your personal information. This Privacy Policy explains how we collect, use, and safeguard your data when you use our movie streaming service.'],
        ['Information We Collect', '• Personal Information: Name, email, and profile details you provide\n• Usage Data: Movies watched, search history, and preferences\n• Device Information: Device type, operating system, and app version\n• Payment Information: Transaction details (processed securely)'],
        ['How We Use Your Information', 'We use your information to provide and improve our service, personalize your experience, process payments, and communicate with you about updates or promotional offers.'],
        ['Data Security', 'Your data is protected using industry-standard encryption and security measures. We never sell your personal information to third parties.'],
        ['Your Rights', 'You have the right to access, update, or delete your personal information. You may also opt out of promotional communications at any time through your account settings.'],
        ['Changes to This Policy', 'We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new policy on this page.'],
      ]}
      footer={['Questions?', `If you have any questions about this Privacy Policy, please contact us at ${SUPPORT_EMAIL}`]}
    />
  );
}

export function Terms() {
  return (
    <LegalPage
      title="Terms of Service"
      heading="Terms of Service"
      intro="By using Cinehubs, you agree to these terms. Please read them carefully."
      sections={[
        ['1. Service Overview', 'Cinehubs provides streaming entertainment services including movies and TV shows. Content availability varies by region and subscription plan.'],
        ['2. Account Registration', 'You must create an account to access most features. You are responsible for maintaining the security of your account and password. Notify us immediately of any unauthorized access.'],
        ['3. Subscription & Billing', '• Subscriptions are billed on a recurring basis\n• You may cancel anytime through account settings\n• Refunds are not provided for partial months\n• We may change pricing with 30 days notice'],
        ['4. Acceptable Use', 'You agree not to:\n• Share account credentials outside your household\n• Download or redistribute content illegally\n• Circumvent any security measures\n• Use the service for commercial purposes'],
        ['5. Content License', 'Content is provided for personal, non-commercial use. All rights remain with their respective owners. We reserve the right to remove content at any time.'],
        ['6. Disclaimer', 'Cinehubs is provided "as is" without warranties of any kind. We do not guarantee uninterrupted service or error-free content.'],
        ['7. Limitation of Liability', 'We shall not be liable for any indirect damages arising from your use of the service. Our total liability shall not exceed the amount paid in the last billing period.'],
        ['8. Termination', 'We may suspend or terminate your account for violations of these terms. You may terminate your account at any time through the app settings.'],
        ['9. Changes to Terms', 'We may modify these terms. Continued use of the service constitutes acceptance of updated terms.'],
      ]}
      footer={['Contact Support', `For questions about these terms, contact us at ${SUPPORT_EMAIL}`]}
    />
  );
}
