import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import Stripe from "https://esm.sh/stripe@14?target=deno"

const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!, {
  apiVersion: '2023-10-16',
  httpClient: Stripe.createFetchHttpClient(),
})

const supabaseUrl = Deno.env.get('SUPABASE_URL')!
const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET')!

serve(async (req) => {
  const signature = req.headers.get('Stripe-Signature')!
  const body = await req.text()

  let event: Stripe.Event
  try {
    event = await stripe.webhooks.constructEventAsync(body, signature, webhookSecret)
  } catch (err) {
    return new Response(JSON.stringify({ error: "Invalid request" }), { status: 400 })
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey)

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session
      const email = session.customer_email
      const customerId = session.customer as string
      const subscriptionId = session.subscription as string

      // Determine plan from price
      const sub = await stripe.subscriptions.retrieve(subscriptionId)
      const priceId = sub.items.data[0]?.price.id
      const plan = priceId === Deno.env.get('STRIPE_PRICE_ID_ENTERPRISE') ? 'enterprise' : 'pro'
      const maxTokens = plan === 'enterprise' ? 999 : 10

      const { error } = await supabase.from('profiles').update({
        role: plan,
        subscription_status: 'active',
        subscription_plan: plan,
        stripe_customer_id: customerId,
        subscription_end: new Date(sub.current_period_end * 1000).toISOString(),
        max_watchlist_tokens: maxTokens,
        updated_at: new Date().toISOString(),
      }).eq('email', email)

      if (error) {
        console.error('checkout.session.completed: failed to update profile by email', { email, error })
        return new Response(JSON.stringify({ error: 'DB update failed' }), { status: 500 })
      }

      break
    }

    case 'customer.subscription.updated': {
      const sub = event.data.object as Stripe.Subscription
      const customerId = sub.customer as string

      const { error } = await supabase.from('profiles').update({
        subscription_status: sub.status,
        subscription_end: new Date(sub.current_period_end * 1000).toISOString(),
        updated_at: new Date().toISOString(),
      }).eq('stripe_customer_id', customerId)

      if (error) {
        console.error('customer.subscription.updated: failed to update profile', { customerId, error })
        return new Response(JSON.stringify({ error: 'DB update failed' }), { status: 500 })
      }

      break
    }

    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription
      const customerId = sub.customer as string

      const { error } = await supabase.from('profiles').update({
        role: 'free',
        subscription_status: 'cancelled',
        subscription_plan: 'free',
        max_watchlist_tokens: 3,
        updated_at: new Date().toISOString(),
      }).eq('stripe_customer_id', customerId)

      if (error) {
        console.error('customer.subscription.deleted: failed to update profile', { customerId, error })
        return new Response(JSON.stringify({ error: 'DB update failed' }), { status: 500 })
      }

      break
    }

    case 'invoice.payment_failed': {
      const invoice = event.data.object as Stripe.Invoice
      const customerId = invoice.customer as string

      const { error } = await supabase.from('profiles').update({
        subscription_status: 'past_due',
        updated_at: new Date().toISOString(),
      }).eq('stripe_customer_id', customerId)

      if (error) {
        console.error('invoice.payment_failed: failed to update profile', { customerId, error })
        return new Response(JSON.stringify({ error: 'DB update failed' }), { status: 500 })
      }

      break
    }
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { 'Content-Type': 'application/json' },
    status: 200,
  })
})
