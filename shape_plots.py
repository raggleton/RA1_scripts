"""

This script makes data VS background plots, but gets the backgrounds from
DATA control region shape, not MC. To do this, we define several control regions
(for each BG source), use MC to calculate transfer factors, then scale the
data control region plot by that factor. Oh yeah and whack in stat + syst
uncertainties, latter from closure tests.

We do this for bins of Njets, Nbtag, HT. And we look at lots of variables.

And we make it look b-e-a-utiful.

Robin Aggleton

"""

import plot_grabber as grabr
import ROOT as r
from itertools import product, izip
import math
import numpy as np


r.TH1.SetDefaultSumw2(True)
r.gStyle.SetOptStat(0)
r.gROOT.SetBatch(1)
r.gStyle.SetOptFit(1111)

ROOTdir = "/Users/robina/Dropbox/AlphaT/Root_Files_28Nov_aT_0p53_v1/"

# Variable(s) you want to plot
# "MHT", "AlphaT", "Meff", "dPhi*", "jet variables", "MET (corrected)", "MHT/MET (corrected)", "Number_Good_vertices",
plot_vars = ["AlphaT", "JetMultiplicity", "LeadJetPt", "LeadJetEta",
             "SecondJetPt", "SecondJetEta", "HT", "MHT", "MET_Corrected", "MET",
             "MHTovMET", "ComMinBiasDPhi_acceptedJets", "EffectiveMass", "Number_Btags", "Number_Good_verticies"]

# Where you want to store plots
# And what you want to call the plots - will be out_dir/out_stem_<var>_<njet>_<btag>_<htbin>.pdf
out_dir = "."
out_stem = "plot"

# Define region bins
HTbins = ["200_275", "275_325", "325_375", "375_475", "475_575",
          "575_675", "675_775", "775_875", "875_975", "975_1075", "1075"][3:]
ht_scheme = ["incl", "excl"][0]  # option for individual bin, or inclusive
n_j = ["le3j", "ge4j", "ge2j"][:2]
n_b = ["eq0b", "eq1b", "eq2b", "eq3b", "ge0b", "ge1b"][:2]

# MC processes that go into transfer factors
processes_mc_ctrl = ['DY', 'DiBoson', 'TTbar', 'WJets', 'Zinv', 'SingleTop']

processes_mc_signal_le1b = {"OneMuon": ['DY', 'DiBoson', 'TTbar', 'WJets', 'SingleTop'],
                            "DiMuon": ['Zinv']}

processes_mc_signal_ge2b = {"OneMuon": ['DY', 'DiBoson', 'TTbar', 'WJets', 'SingleTop', 'Zinv'],
                            "DiMuon": []}  # for >= 2btags dimu region not used

# Control regions to get data shapes (+ proper titles for legend etc)
ctrl_regions = {"OneMuon": "Single #mu BG", "DiMuon": "#mu#mu BG"}

# Sytematics on TF (as a %). Fn on njets & HT
tf_systs = {
    "le3j": {"200_275": 4, "275_325": 6, "325_375": 6, "375_475": 8, "475_575": 8, "575_675": 12, "675_775": 12, "775_875": 17, "875_975": 17, "975_1075": 19, "1075": 19},
    "ge4j": {"200_275": 6, "275_325": 6, "325_375": 11, "375_475": 11, "475_575": 11, "575_675": 18, "675_775": 18, "775_875": 20, "875_975": 20, "975_1075": 26, "1075": 26}
}

class Ratio_Plot():
    """
    Class to make a ratio plot
    """

    def __init__(self, var, njet, btag, htbins, rebin, log):
        self.var = var
        self.njet = njet
        self.btag = btag
        self.htbins = htbins
        self.rebin = rebin #hmm get rid of these?
        self.log = log # ditto
        self.c = r.TCanvas()
        self.up = r.TPad("u","",0.01,0.25,0.99,0.99)
        self.dp = r.TPad("d","",0.01,0.01,0.99,0.25)
        self.dp.SetBottomMargin(1.3*self.dp.GetBottomMargin())
        self.hist_data_signal = None
        self.component_hists = []
        self.transfer_factors = {}
        self.shape_stack = r.THStack("shape_stack", "")
        self.error_hists_stat = []
        self.error_hists_stat_syst = []
        self.stdtxt = self.make_standard_text()
        self.cuttxt = self.make_bin_text()
        self.leg = self.make_legend()

        self.c.cd()
        # Now make plots
        self.make_hists()
        self.make_main_plot(self.up)
        self.c.cd()
        self.make_ratio_plot(self.dp, self.hist_data_signal, self.error_hists_stat_syst[-1])
        self.c.cd()


    def save(self, name=None):
        self.c.cd()
        if not name:
            self.c.SaveAs("%s/%s_%s_%s_%s_%s.pdf" % (out_dir, out_stem, self.var, self.njet, self.btag, self.htbins))
        else:
            self.c.SaveAs(name)


    def color_hist(self, hist, color):
        """
        Set marker/line/fill color for histogram
        """
        hist.SetLineColor(color)
        hist.SetFillColor(color)
        hist.SetMarkerColor(color)


    def style_hist(self, hist, region):
        """
        Do some aesthetic stylings on hists.
        """
        hist.Rebin(self.rebin)
        if region == "OneMuon":
            self.color_hist(hist, r.kViolet + 1)
        elif region == "DiMuon":
            self.color_hist(hist, r.kOrange)
        elif region == "Data":
            hist.SetMarkerColor(r.kBlack)
            # hist.SetMarkerSize(2)
            hist.SetMarkerStyle(20)
            hist.SetLineColor(r.kBlack)


    def style_hist_err1(self, hist):
        """
        Do some aesthetic stylings on error bars.
        """
        hist.SetMarkerStyle(0)
        hist.SetMarkerSize(0)
        hist.SetLineColor(r.kGray + 3)
        hist.SetLineWidth(0)
        hist.SetFillColor(r.kGray + 3)
        hist.SetFillStyle(3002)


    def style_hist_err2(self, hist):
        """
        Do some alternate stylings on error bars.
        """
        hist.SetMarkerStyle(0)
        hist.SetMarkerSize(0)
        hist.SetLineColor(r.kGray + 3)
        hist.SetLineWidth(0)
        hist.SetFillColor(r.kGray + 3)
        hist.SetFillStyle(3013)


    def style_hist_ratio(self, hist):
        """
        Do some stylings on ratio plot
        """
        hist.SetMarkerColor(r.kBlack)
        # hist.SetMarkerSize(2)
        hist.SetMarkerStyle(20)
        hist.SetLineColor(r.kBlack)
        ratioY = self.up.GetAbsHNDC() / self.dp.GetAbsHNDC()
        # ratioX = self.up.GetAbsVNDC() / self.dp.GetAbsVNDC()
        # apparently hist.GetYaxis().Set... doesn't really work here?
        hist.SetTitleSize(hist.GetYaxis().GetTitleSize()*ratioY, "Y")
        hist.SetLabelSize(hist.GetYaxis().GetLabelSize()*ratioY, "Y")
        hist.SetTitleOffset(hist.GetYaxis().GetTitleOffset()/ratioY, "Y")
        hist.SetLabelOffset(hist.GetYaxis().GetLabelOffset()*ratioY, "Y")
        hist.GetYaxis().SetNdivisions(6+(100*6))

        hist.SetTitleSize(hist.GetXaxis().GetTitleSize()*ratioY, "X")
        hist.SetLabelSize(hist.GetXaxis().GetLabelSize()*ratioY, "X")
        # hist.SetTitleOffset(hist.GetXaxis().GetTitleOffset()/ratioY, "X")
        hist.SetTitleOffset(9999, "X")
        hist.SetLabelOffset(hist.GetXaxis().GetLabelOffset()*ratioY, "X")


    def title_axes(self, hist, xtitle, ytitle="Events"):
        """
        Apply title to axes, do offsets, sizes
        """
        hist.SetXTitle(xtitle)
        hist.SetYTitle(ytitle)
        hist.SetTitleOffset(hist.GetTitleOffset("Y") * 1.2, "Y")


    def make_legend(self):
        """
        Generate blank legend
        """
        leg = r.TLegend(0.68, 0.49, 0.87, 0.72)
        leg.SetFillColor(0)
        leg.SetFillStyle(0)
        leg.SetLineColor(0)
        leg.SetLineStyle(0)
        leg.SetLineWidth(0)
        return leg


    def make_standard_text(self):
        """
        Generate standard boring text
        """
        t = r.TPaveText(0.66, 0.73, 0.87, 0.87, "NDC")
        t.AddText("CMS 2012, #sqrt{s} = 8 TeV")
        t.AddText("")
        t.AddText("#int L dt = 18.493 fb^{-1}")
        t.SetFillColor(0)
        t.SetFillStyle(0)
        t.SetLineColor(0)
        t.SetLineStyle(0)
        t.SetLineWidth(0)
        return t


    def make_bin_text(self):
        """
        Generate label of which bin
        """
        t = r.TPaveText(0.1, 0.91, 0.5, 0.95, "NDC")
        b_str = grabr.btag_string(self.btag) if grabr.btag_string(self.btag) else "geq 0 btag"
        tt = t.AddText("%s, %s, HT bin %s" % (self.njet, b_str, self.htbins))
        tt.SetTextAlign(12)
        t.SetFillColor(0)
        t.SetFillStyle(0)
        t.SetLineColor(0)
        t.SetLineStyle(0)
        t.SetLineWidth(0)
        return t


    def set_syst_errors(self, h):
        """
        Turns stat errors into stat+syst errors using LUT at top
        """
        for i in range(1, h.GetNbinsX() + 1):
            syst =  h.GetBinContent(i) * tf_systs[self.njet][self.htbins] / 100.
            err = np.hypot(h.GetBinError(i),syst)
            h.SetBinError(i, err)


    def make_hists(self):
        """
        Makes component histograms for any plot: data in signal region, and a
        list of histograms that are BG estimates from doing
        data_control * transfer factor.
        Each hist in the list corresponds to one control region.
        Basically for each of the control regions, it gets data in
        control region, MC in signal & control regions (for all SM processes),
        and data in signal region. Then calculate transfer factor
        (MC_signal / MC_control), and scale data_control by that factor.

        Returns list comprising of data hist followed by component histograms
        in their own list (one for each control region)
        """

        for ctrl in ctrl_regions:
            print "**** DOING", ctrl

            if "Muon" in ctrl:
                f_start = "Muon"
            elif "Photon" in ctrl:
                f_start = "Photon"
            # else:
                # f_start = "Had"

            # Data in control region:
            hist_data_control = grabr.grab_plots(f_path="%s/%s_Data.root" % (ROOTdir, f_start),
                                                 sele=ctrl, h_title=self.var, njet=self.njet, btag=self.btag, ht_bins=self.htbins)
            hist_data_control.SetName(ctrl)  # for styling later

            # MC in signal region
            if "0" in self.btag or "1" in self.btag:
                processes = processes_mc_signal_le1b
            else:
                processes = processes_mc_signal_ge2b

            print "MC in signal region:"
            hist_mc_signal = None
            for p in processes[ctrl]:
                MC_signal_tmp = grabr.grab_plots(f_path="%s/Had_%s.root" % (ROOTdir, p),
                                                 sele="Had", h_title=self.var, njet=self.njet, btag=self.btag, ht_bins=self.htbins)
                print p, MC_signal_tmp.Integral()
                if not hist_mc_signal:
                    hist_mc_signal = MC_signal_tmp.Clone("MC_signal")
                else:
                    hist_mc_signal.Add(MC_signal_tmp)


            # MC in control region
            print "MC in control region:"
            hist_mc_control = None
            for p in processes_mc_ctrl:
                MC_ctrl_tmp = grabr.grab_plots(f_path="%s/%s_%s.root" % (ROOTdir, f_start, p),
                                               sele=ctrl, h_title=self.var, njet=self.njet, btag=self.btag, ht_bins=self.htbins)
                print p, MC_ctrl_tmp.Integral()
                if not hist_mc_control:
                    hist_mc_control = MC_ctrl_tmp.Clone()
                else:
                    hist_mc_control.Add(MC_ctrl_tmp)


            mc_signal_err = r.Double(-1.)
            mc_signal_integral = hist_mc_signal.IntegralAndError(1, hist_mc_signal.GetNbinsX(), mc_signal_err)
            mc_control_err = r.Double(-1.)
            mc_control_integral = hist_mc_control.IntegralAndError(1, hist_mc_control.GetNbinsX(), mc_control_err)
            data_control_err = r.Double(-1.)
            data_control_integral = hist_data_control.IntegralAndError(1, hist_data_control.GetNbinsX(), data_control_err)

            print ctrl
            print "Data control: %.3f +/- %.3f" % (data_control_integral, data_control_err)
            print "MC signal: %.3f +/- %.3f" % (mc_signal_integral, mc_signal_err)
            print "MC control: %.3f +/- %.3f" % (mc_control_integral, mc_control_err)

            # Divide, multiply, and add to total shape
            # ROOT's Multiply()/Divide() are bin-by-bin. To propagate the errors,
            # we need copies of the hists we want to multiply/divide, with ALL bins
            # set to Integral +/- (Error on Integral)
            hist_mc_signal_factor = hist_mc_signal.Clone()
            hist_mc_control_factor = hist_mc_control.Clone()

            for i in range(1, 1 + hist_mc_signal_factor.GetNbinsX()):
                hist_mc_signal_factor.SetBinContent(i, mc_signal_integral)
                hist_mc_signal_factor.SetBinError(i, mc_signal_err)
                hist_mc_control_factor.SetBinContent(i, mc_control_integral)
                hist_mc_control_factor.SetBinError(i, mc_control_err)

            hist_mc_signal_factor.Divide(hist_mc_control_factor)
            hist_data_control.Multiply(hist_mc_signal_factor)
            print "Transfer Factor for %s: %.3f +/- %.3f" % (ctrl, hist_mc_signal_factor.GetBinContent(1), hist_mc_signal_factor.GetBinError(1))
            self.component_hists.append(hist_data_control)
            self.transfer_factors[ctrl] = hist_mc_signal_factor.GetBinContent(1)
            print ctrl, "estimate:", hist_data_control.Integral()

        # Get data hist
        self.hist_data_signal = grabr.grab_plots(f_path="%s/Had_Data.root" % ROOTdir,
                                            sele="Had", h_title=self.var, njet=self.njet, btag=self.btag, ht_bins=self.htbins)
        self.style_hist(self.hist_data_signal, "Data")

        print "Data SR:", self.hist_data_signal.Integral()


    def make_main_plot(self, pad):
        """
        For a given variable, NJet, Nbtag, HT bins,
        makes data VS background plot, where BG is from data control regions.
        """
        pad.Draw()
        pad.cd()
        # Get our data & BG shapes & TFs
        # make_hists(self.var, self.njet, self.btag, self.htbins)


        # Make stack of backgrounds, and put error bands on each contribution:
        # There is a ROOT bug whereby if you try and make copies of the hists,
        # put into a THStack, and tell it to plot with E2 and set a fill style
        # like 3013, only the last hist will actually render properly,
        # others will be blocky. So to avoid this we build up cumulative TH1s and
        # then draw those ontop of the main block colours. (5.34.21 MacOSX w/Cocoa)
        #
        # If you only want an error band on the total, then it's easy: make a clone
        # of stack.Last(), and Draw("E2").

        # Want to add hists to THStack by ascending Integral()
        self.component_hists.sort(key=lambda hist: hist.Integral())
        # Loop through shape components: mod style, add to THStack, make error bars
        for h in self.component_hists:
            # Some shimmer BEFORE adding to stack
            self.style_hist(h, h.GetName())
            self.shape_stack.Add(h.Clone())
            # copies for stat/syst error bars
            if not self.error_hists_stat:
                h_stat = h.Clone()
                self.style_hist_err1(h_stat)
                self.error_hists_stat = [h_stat]

                h_syst = h.Clone()
                self.style_hist_err2(h_syst)
                self.set_syst_errors(h_syst)
                self.error_hists_stat_syst = [h_syst]
            else:
                h_stat = self.error_hists_stat[-1].Clone()
                h_stat.Add(h)
                self.style_hist_err1(h_stat)
                self.error_hists_stat.append(h_stat)

                h_syst = self.error_hists_stat_syst[-1].Clone()
                h_syst.Add(h)
                self.style_hist_err2(h_syst)
                self.set_syst_errors(h_syst)
                self.error_hists_stat_syst.append(h_syst)

        print "BG estimate from data:", self.error_hists_stat[-1].Integral()

        # add entries to the legend
        self.leg.AddEntry(self.hist_data_signal, "Data + stat. error", "pl")
        for h in reversed(self.component_hists):
            self.leg.AddEntry(h, ctrl_regions[h.GetName()], "f")
        self.leg.AddEntry(self.error_hists_stat[-1], "Stat. error", "F")
        self.leg.AddEntry(self.error_hists_stat_syst[-1], "Stat. + syst. error", "F")

        # Finally draw all the pieces
        pad.SetLogy(self.log)
        pad.SetTicks()

        # Urgh trying to set y axis maximum correctly is a massive ball ache,
        # since THStack doesn't account for error properly (that's now 2 ROOT bugs)
        sum = self.shape_stack.GetStack().Last()  # the "sum" of component hists
        max_stack = sum.GetMaximum() + sum.GetBinError(sum.GetMaximumBin())
        max_data = self.hist_data_signal.GetMaximum() + \
                   self.hist_data_signal.GetBinError(self.hist_data_signal.GetMaximumBin())

        if max_stack > max_data:
            self.shape_stack.Draw("HIST")
            if self.log:
                self.shape_stack.SetMaximum(max_stack * 5.)
            else:
                self.shape_stack.SetMaximum(max_stack * 1.1)
            self.shape_stack.Draw("HIST")
            self.hist_data_signal.Draw("SAME")
        else:
            self.hist_data_signal.Draw()
            self.shape_stack.Draw("HIST SAME")
            self.hist_data_signal.Draw("SAME")

        self.hist_data_signal.Draw("SAME")
        self.c.SaveAs("test.pdf")

        [h.Draw("E2 SAME") for h in self.error_hists_stat]
        [h.Draw("E2 SAME") for h in self.error_hists_stat_syst]
        pad.RedrawAxis()  # important to put axis on top of all plots
        self.title_axes(self.hist_data_signal, self.var, "Events")
        self.title_axes(self.shape_stack.GetHistogram(), self.var, "Events")
        self.leg.Draw()
        self.stdtxt.Draw("SAME")
        self.cuttxt.Draw("SAME")

        # if save:
        #     c.SaveAs("%s/%s_%s_%s_%s_%s.pdf" % (out_dir, out_stem, var, njet, btag, htbins))


    def make_ratio_plot(self, pad, h_data, h_mc):
        """
        Makes the little data/MC ratio plot
        """
        pad.Draw()
        pad.cd()
        pad.SetTicks()

        self.hist_ratio = h_data.Clone("ratio")
        self.hist_ratio.Divide(h_mc.Clone())

        # for i in range(1,self.hist_ratio.GetNbinsX()+1):
        #     print self.hist_ratio.GetBinContent(i)

        self.hist_ratio.GetYaxis().SetTitle("Data/MC")
        self.style_hist_ratio(self.hist_ratio)

        self.hist_ratio.Draw("EP")

        self.l = r.TLine(self.hist_ratio.GetXaxis().GetXmin(), 1, self.hist_ratio.GetXaxis().GetXmax() , 1)
        self.l.SetLineWidth(2)
        self.l.SetLineStyle(2)
        self.l.Draw()



def make_plot_bins(var):
    """
    For a given variable, makes data VS background plots for all the
    relevant HT, Njets, Nbtag bins
    """
    # for v in var:
    #     print "Doing plots for", v
    #     # for njet, btag, ht_bins in product(n_j, n_b, HTbins):
    #     rebin = 2
    #     if v in ["Number_Btags", "JetMultiplicity"]:
    #         rebin = 1
    #     elif v in ['AlphaT', 'ComMinBiasDPhi']:
    #         rebin = 10

    #     log = False
    #     if v in ["ComMinBiasDPhi", "AlphaT"]:
    #         log = True
    #         # make_plot(v, njet, btag, ht_bins, rebin, log)
    #         # make_plot(v, "le3j", "eq0b", "375_475", rebin, log)

    #     plot = Ratio_Plot(v, "le3j", "eq0b", "375_475", rebin, log)
    plot = Ratio_Plot("LeadJetEta", "le3j", "eq0b", "375_475", 2, False)
    plot.save()
        # make_plot(v, "le3j", "eq0b", "375_475", rebin, log)
    # make_plot("LeadJetEta", "le3j", "eq0b", "475_575", rebin=2, log=False)
    # make_plot("SecondJetPt", "le3j", "eq0b", "375_475", rebin=2, log=False)
    # make_plot("SecondJetPt", "le3j", "eq2b", "475_575", rebin=2, log=False)


if __name__ == "__main__":
    print "Making lots of data VS bg plots..."
    make_plot_bins(plot_vars)
