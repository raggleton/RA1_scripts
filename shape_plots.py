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

# input files
ROOTdir = "/Users/robina/Dropbox/AlphaT/Root_Files_28Nov_aT_0p53_v1/"

# Variable(s) you want to plot
# "MHT", "AlphaT", "Meff", "dPhi*", "jet variables", "MET (corrected)", "MHT/MET (corrected)", "Number_Good_vertices",
plot_vars = ["AlphaT", "JetMultiplicity", "LeadJetPt", "LeadJetEta",
             "SecondJetPt", "SecondJetEta", "HT", "MHT", "MET_Corrected",
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
        self.rebin = rebin
        self.log = log
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
        hist.GetYaxis().SetTitle("Data/MC")
        ratioY = self.up.GetAbsHNDC() / self.dp.GetAbsHNDC()
        # ratioX = self.up.GetAbsVNDC() / self.dp.GetAbsVNDC()
        # apparently hist.GetYaxis().Set... doesn't really work here?
        hist.SetTitleSize(hist.GetYaxis().GetTitleSize()*ratioY, "Y")
        hist.SetLabelSize(hist.GetYaxis().GetLabelSize()*ratioY, "Y")
        hist.SetTitleOffset(hist.GetYaxis().GetTitleOffset()/ratioY, "Y")
        hist.SetLabelOffset(hist.GetYaxis().GetLabelOffset()*ratioY, "Y")
        hist.GetYaxis().SetNdivisions(6+(100*6))
        hist.GetYaxis().SetRangeUser(0, 2.0)

        hist.SetTitleSize(hist.GetXaxis().GetTitleSize()*ratioY, "X")
        hist.SetLabelSize(hist.GetXaxis().GetLabelSize()*ratioY, "X")
        # hist.SetTitleOffset(hist.GetXaxis().GetTitleOffset()/ratioY, "X")
        hist.SetTitleOffset(9999, "X")
        hist.SetLabelOffset(hist.GetXaxis().GetLabelOffset()*ratioY, "X")
        hist.GetXaxis().SetTickLength(hist.GetXaxis().GetTickLength()*ratioY)


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


    def autorange_xaxis(self, h_1, h_2):
        """
        Return x axis range such that only filled bins are shown,
        for both h_1 and h_2.
        Plus a bit of padding on the left, and a lot more on the right
        """
        # store values that mark edge of contents
        low_1 = -1000000.
        low_2 = -1000000.
        high_1 = 1000000.
        high_2 = 1000000.

        prev_1 = 0.
        prev_2 = 0.

        found_low_1 = False
        found_low_2 = False

        for i in range(1, 1 + h_1.GetNbinsX()):
            if not found_low_1 and not prev_1 and h_1.GetBinContent(i) > 0:
                low_1 = h_1.GetBinLowEdge(i)
                prev_1 = h_1.GetBinContent(i)
                found_low_1 = True
            if not found_low_2 and not prev_2 and h_2.GetBinContent(i) > 0:
                low_2 = h_2.GetBinLowEdge(i)
                prev_2 = h_2.GetBinContent(i)
                found_low_2 = True
            if prev_1 and not h_1.GetBinContent(i):
                high_1 = h_1.GetBinLowEdge(i+1)
                prev_1 = h_1.GetBinContent(i)
            if prev_2 and not h_2.GetBinContent(i):
                high_2 = h_2.GetBinLowEdge(i+1)
                prev_2 = h_2.GetBinContent(i)

        xmin = low_1 if low_1 < low_2 else low_2
        xmax = high_1 if high_1 > low_2 else high_2
        # xmin -= (2*h_1.GetBinWidth(1))  # add little bit of padding to LHS
        xmax += 0.4 * (xmax-xmin)  # add some space to RHS
        print xmin, xmax
        return xmin, xmax


    def set_syst_errors(self, h):
        """
        Turns stat errors into stat+syst errors using LUT at top
        """
        for i in range(1, h.GetNbinsX() + 1):
            syst =  h.GetBinContent(i) * tf_systs[self.njet][self.htbins] / 100.
            err = np.hypot(h.GetBinError(i), syst)
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
            print "Data in control reigon:", hist_data_control.Integral()

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

            print "Total:", hist_mc_signal.Integral()

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

            print "Total:", hist_mc_control.Integral()

            hist_data_control.Multiply(hist_mc_signal)
            hist_data_control.Divide(hist_mc_control)
            self.component_hists.append(hist_data_control)
            print ctrl, "Estimate:", hist_data_control.Integral()

        # Get data hist
        self.hist_data_signal = grabr.grab_plots(f_path="%s/Had_Data.root" % ROOTdir,
                                            sele="Had", h_title=self.var, njet=self.njet, btag=self.btag, ht_bins=self.htbins)

        print "Data SR:", self.hist_data_signal.Integral()


    def make_main_plot(self, pad):
        """
        For a given variable, NJet, Nbtag, HT bins,
        makes data VS background plot, where BG is from data control regions.
        """
        pad.Draw()
        pad.cd()

        self.style_hist(self.hist_data_signal, "Data")

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
            self.shape_stack.Add(h)
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

        # Get x range - but can only set it for the stack once you've drawn it (fail)
        xmin, xmax = self.autorange_xaxis(self.hist_data_signal, self.shape_stack.GetStack().Last())
        self.hist_data_signal.SetAxisRange(xmin, xmax, "X")

        # Urgh trying to set y axis maximum correctly is a massive ball ache,
        # since THStack doesn't account for error properly (that's now 2 ROOT bugs)
        sum = self.shape_stack.GetStack().Last()  # the "sum" of component hists
        max_stack = sum.GetMaximum() + self.error_hists_stat_syst[-1].GetBinError(sum.GetMaximumBin())
        max_data = self.hist_data_signal.GetMaximum() + \
                   self.hist_data_signal.GetBinError(self.hist_data_signal.GetMaximumBin())

        if max_stack > max_data:
            self.shape_stack.Draw("HIST")
            self.shape_stack.GetXaxis().SetRangeUser(xmin, xmax)
            r.gPad.Update();
            ymin = r.gPad.GetUymin()
            if self.log:
                self.shape_stack.SetMaximum(max_stack * 5.)
                if (ymin <= 0.): ymin = 0.001
            else:
                self.shape_stack.SetMaximum(max_stack * 1.1)
            self.shape_stack.SetMinimum(ymin)  # setting maximum somehow FUs min - do manually
            self.shape_stack.Draw("HIST")
            self.hist_data_signal.Draw("SAME")
        else:
            self.hist_data_signal.Draw()
            self.shape_stack.Draw("HIST SAME")
            self.shape_stack.GetXaxis().SetRangeUser(xmin, xmax)
            self.hist_data_signal.Draw("SAME")

        [h.GetXaxis().SetRangeUser(xmin, xmax) for h in self.error_hists_stat]
        [h.Draw("E2 SAME") for h in self.error_hists_stat]
        [h.GetXaxis().SetRangeUser(xmin, xmax) for h in self.error_hists_stat_syst]
        [h.Draw("E2 SAME") for h in self.error_hists_stat_syst]
        self.hist_data_signal.Draw("SAME")  # data points ontop of everything
        pad.RedrawAxis()  # important to put axis on top of all plots
        self.title_axes(self.hist_data_signal, self.var, "Events")
        self.title_axes(self.shape_stack.GetHistogram(), self.var, "Events")
        self.leg.Draw()
        self.stdtxt.Draw("SAME")
        self.cuttxt.Draw("SAME")


    def make_ratio_plot(self, pad, h_data, h_mc):
        """
        Makes the little data/MC ratio plot
        """
        pad.Draw()
        pad.cd()
        pad.SetTicks()

        self.hist_ratio = h_data.Clone("ratio")
        self.hist_ratio.Divide(h_mc.Clone())
        self.style_hist_ratio(self.hist_ratio)
        self.hist_ratio.Draw("EP")
        r.gPad.Update();
        min = self.hist_ratio.GetXaxis().GetXmin() # NOPE DOESN'T WORK
        max = self.hist_ratio.GetXaxis().GetXmax()
        xmin, xmax = self.autorange_xaxis(h_data, h_mc)
        # For some unbelievably fucking stupid reason, I have to use
        # gPad.GetUxmax for upper edge, but xmin for lower edge as
        # gPad.GetUxmin mis reports it
        # And GetXaxis.GetMax/Min doesn't even work, it ignores the fact
        # I've told it to change range
        # Stupid piece of shit
        self.l = r.TLine(xmin, 1, r.gPad.GetUxmax(), 1)
        self.l.SetLineWidth(2)
        self.l.SetLineStyle(2)
        self.l.Draw()


def make_plot_bins(var):
    """
    For a given variable, makes data VS background plots for all the
    relevant HT, Njets, Nbtag bins
    """
    for v in var:
        print "Doing plots for", v
    #     # for njet, btag, ht_bins in product(n_j, n_b, HTbins):
        rebin = 2
        if v in ["Number_Btags", "JetMultiplicity", "MHTovMET"]:
            rebin = 1
        elif v in ['ComMinBiasDPhi_acceptedJets']:
            rebin = 10
        elif v in ['AlphaT', 'ComMinBiasDPhi', 'ComMinBiasDPhi_acceptedJets']:
            rebin = 10

        log = False
        if v in ["ComMinBiasDPhi", "ComMinBiasDPhi_acceptedJets", "AlphaT", "HT"]:
            log = True

        plot = Ratio_Plot(v, "le3j", "eq0b", "375_475", rebin, log)
        # plot = Ratio_Plot(v, "ge4j", "eq0b", "475_575", rebin, log)
        plot.save()

    # For testing
    # plot = Ratio_Plot("AlphaT", "ge4j", "eq0b", "475_575", 10, True)
    # plot.save()


if __name__ == "__main__":
    print "Making lots of data VS bg plots..."
    make_plot_bins(plot_vars)
