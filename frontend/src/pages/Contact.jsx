import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import FadeSection from "../components/FadeSection";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", subject: "", message: "" });
  const [submitting, setSubmitting] = useState(false);

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.message) {
      toast.error("Please complete name, email and message.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/contact`, {
        name: form.name,
        email: form.email,
        subject: form.subject || "Inquiry from Mossero website",
        message: form.message,
      });
      toast.success("Thank you", {
        description: res.data.message || "We have received your message.",
      });
      setForm({ name: "", email: "", subject: "", message: "" });
    } catch (err) {
      toast.error("Unable to send", {
        description: err?.response?.data?.detail || "Please try again shortly.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="contact-page" className="bg-cream pt-32 lg:pt-44 pb-32">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-12">
        <div className="text-center mb-20">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            Concierge
          </p>
          <h1 className="font-serif text-5xl lg:text-7xl text-ink leading-tight">
            Write to us.
          </h1>
          <hr className="gold-divider-short mt-12" />
        </div>

        <FadeSection className="grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-24">
          <div className="lg:col-span-5">
            <p className="text-[11px] uppercase tracking-luxe text-gold mb-6">
              The Maison
            </p>
            <h3 className="font-serif text-3xl lg:text-4xl text-ink leading-snug mb-10">
              For private orders, press, and invitations to the atelier.
            </h3>
            <hr className="gold-divider-short mb-10" />
            <div className="space-y-6 text-sm text-ink/75 font-light leading-[1.9]">
              <div>
                <p className="text-[10px] uppercase tracking-luxe text-ink mb-2">
                  Email
                </p>
                <a
                  href="mailto:mossero.in@gmail.com"
                  className="text-base hover:text-gold transition-colors"
                  data-testid="contact-email"
                >
                  mossero.in@gmail.com
                </a>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-luxe text-ink mb-2">
                  Hours
                </p>
                <p>Monday — Saturday, 10:00 — 19:00 IST</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-luxe text-ink mb-2">
                  Web
                </p>
                <p>www.mossero.in</p>
              </div>
            </div>
          </div>

          <form
            onSubmit={submit}
            data-testid="contact-form"
            className="lg:col-span-7 space-y-10"
          >
            <div>
              <label className="luxe-label" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                data-testid="contact-name"
                className="luxe-input"
                value={form.name}
                onChange={update("name")}
                required
              />
            </div>
            <div>
              <label className="luxe-label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                data-testid="contact-email-input"
                className="luxe-input"
                value={form.email}
                onChange={update("email")}
                required
              />
            </div>
            <div>
              <label className="luxe-label" htmlFor="subject">
                Subject
              </label>
              <input
                id="subject"
                data-testid="contact-subject"
                className="luxe-input"
                value={form.subject}
                onChange={update("subject")}
              />
            </div>
            <div>
              <label className="luxe-label" htmlFor="message">
                Message
              </label>
              <textarea
                id="message"
                data-testid="contact-message"
                className="luxe-input"
                rows={5}
                value={form.message}
                onChange={update("message")}
                required
              />
            </div>
            <button
              type="submit"
              data-testid="contact-submit"
              className="btn-gold"
              disabled={submitting}
            >
              {submitting ? "Sending…" : "Send Message"}
            </button>
          </form>
        </FadeSection>
      </div>
    </div>
  );
}
